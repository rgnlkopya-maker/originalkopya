from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from app_settings.access import has_access
from core.models import Order
from product_cards.models import ShowroomDraft
from product_cards.showroom_views import _apply_pricing_operations


MONEY = Decimal("0.01")


def _q(value):
    return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)


def _folio_finance(draft, include_items=False):
    items = list(
        draft.items.select_related("product_card__urun")
        .prefetch_related("product_card__materials__material")
        .order_by("product_card__urun__kod", "created_at", "id")
    )

    subtotal = sum(
        (Decimal(item.unit_price or 0) * Decimal(max(1, int(item.quantity or 1))) for item in items),
        Decimal("0"),
    )

    pricing_ops = draft.pricing_operations or []
    vat_multiplier = Decimal("1")

    if pricing_ops or draft.folio_adjustment_target is not None:
        pricing = _apply_pricing_operations(
            subtotal,
            pricing_ops,
            draft.folio_adjustment_target,
        )
        gross_total = pricing["folio_total"]
        for step in pricing["steps"]:
            if step["type"] == "VAT":
                vat_multiplier *= Decimal("1") + (Decimal(str(step["value"])) / Decimal("100"))
    else:
        discount = (
            subtotal * Decimal(draft.discount_rate or 0) / Decimal("100")
            if draft.discount_rate and draft.discount_rate > 0
            else Decimal(draft.overall_discount_amount or 0)
        )
        discount = min(subtotal, max(Decimal("0"), discount))
        taxable = max(Decimal("0"), subtotal - discount)
        vat_rate = max(Decimal("0"), min(Decimal("100"), Decimal(draft.vat_rate or 0)))
        vat_multiplier = Decimal("1") + (vat_rate / Decimal("100"))
        gross_total = taxable * vat_multiplier

    net_total = gross_total / vat_multiplier if vat_multiplier > 0 else gross_total
    net_factor = (net_total / subtotal) if subtotal > 0 else Decimal("0")

    linked_orders_by_item = {}
    if draft.status == "TRANSFERRED":
        for link in draft.order_links.select_related("order").all():
            if link.draft_item_id:
                linked_orders_by_item.setdefault(link.draft_item_id, []).append(link.order)

    total_cost = Decimal("0")
    product_count = set()
    total_qty = 0
    detail_items = []

    for item in items:
        qty = max(1, int(item.quantity or 1))
        total_qty += qty
        code = item.product_card.urun.kod
        product_count.add(code)

        net_unit = Decimal(item.unit_price or 0) * net_factor
        linked_orders = linked_orders_by_item.get(item.id, [])
        if linked_orders:
            row_cost = sum(
                (Decimal(order.toplam_maliyet or 0) * Decimal(order.adet or 1) for order in linked_orders),
                Decimal("0"),
            )
            unit_cost = row_cost / Decimal(qty) if qty else Decimal("0")
        else:
            # Henüz siparişe dönüşmemiş veya eski bağlantısız föylerde ürün kartı maliyeti kullanılır.
            unit_cost = Decimal(item.product_card.toplam_maliyet or 0)
            row_cost = unit_cost * Decimal(qty)
        row_revenue = net_unit * Decimal(qty)
        row_profit = row_revenue - row_cost
        unit_profit = net_unit - unit_cost
        unit_profit_rate = (
            (unit_profit / net_unit) * Decimal("100")
            if net_unit > 0 else Decimal("0")
        )

        total_cost += row_cost

        if include_items:
            detail_items.append({
                "code": code,
                "color": item.color or "—",
                "size": item.size or "—",
                "quantity": qty,
                "description": item.description or "—",
                "net_unit_price": _q(net_unit),
                "unit_cost": _q(unit_cost),
                "unit_profit": _q(unit_profit),
                "unit_profit_rate": _q(unit_profit_rate),
                "row_revenue": _q(row_revenue),
                "row_cost": _q(row_cost),
                "row_profit": _q(row_profit),
            })

    total_profit = net_total - total_cost
    profit_rate = (
        (total_profit / net_total) * Decimal("100")
        if net_total > 0 else Decimal("0")
    )

    return {
        "id": draft.id,
        "customer": draft.customer.ad if draft.customer else "Müşteri seçilmedi",
        "date": draft.created_at,
        "updated_at": draft.updated_at,
        "product_count": len(product_count),
        "total_qty": total_qty,
        "revenue": _q(net_total),
        "gross_total": _q(gross_total),
        "cost": _q(total_cost),
        "profit": _q(total_profit),
        "profit_rate": _q(profit_rate),
        "items": detail_items,
    }


def _order_type_summary(qs):
    revenue = Decimal("0")
    cost = Decimal("0")
    for order in qs:
        sale = Decimal(order.satis_fiyati or 0)
        revenue += sale * Decimal(order.adet or 1)
        # Sipariş finans ekranında siparişe kilitlenmiş maliyet mantığını koru.
        cost += Decimal(order.toplam_maliyet or 0) * Decimal(order.adet or 1)
    profit = revenue - cost
    rate = (profit / revenue * Decimal("100")) if revenue > 0 else Decimal("0")
    return {
        "revenue": _q(revenue),
        "cost": _q(cost),
        "profit": _q(profit),
        "profit_rate": _q(rate),
        "count": qs.count(),
    }


def _date_filter(request, folios, orders):
    start = (request.GET.get("start") or "").strip()
    end = (request.GET.get("end") or "").strip()
    if start:
        folios = folios.filter(created_at__date__gte=start)
        orders = orders.filter(siparis_tarihi__gte=start)
    if end:
        folios = folios.filter(created_at__date__lte=end)
        orders = orders.filter(siparis_tarihi__lte=end)
    return start, end, folios, orders


@login_required
def siparis_finans_raporu(request):
    if not has_access(request.user, "can_view_reports"):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    folios = (
        ShowroomDraft.objects
        .filter(status__in=["APPROVED", "TRANSFERRED"])
        .select_related("customer")
        .prefetch_related("items__product_card__urun", "items__product_card__materials__material", "order_links__order")
        .order_by("-created_at", "-id")
    )
    orders = Order.objects.filter(is_active=True).select_related("musteri")
    start, end, folios, orders = _date_filter(request, folios, orders)

    folio_rows = [_folio_finance(draft) for draft in folios]
    folio_revenue = sum((x["revenue"] for x in folio_rows), Decimal("0"))
    folio_cost = sum((x["cost"] for x in folio_rows), Decimal("0"))
    folio_profit = folio_revenue - folio_cost
    folio_rate = (folio_profit / folio_revenue * Decimal("100")) if folio_revenue > 0 else Decimal("0")

    context = {
        "start": start,
        "end": end,
        "folio_summary": {
            "revenue": _q(folio_revenue),
            "cost": _q(folio_cost),
            "profit": _q(folio_profit),
            "profit_rate": _q(folio_rate),
            "count": len(folio_rows),
        },
        "tekli_summary": _order_type_summary(orders.filter(siparis_tipi="TEKLI")),
        "ozel_summary": _order_type_summary(orders.filter(siparis_tipi="OZEL")),
    }
    return render(request, "reports/siparis_finans_raporu.html", context)


@login_required
def siparis_finans_foyleri(request):
    if not has_access(request.user, "can_view_reports"):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    folios = (
        ShowroomDraft.objects
        .filter(status__in=["APPROVED", "TRANSFERRED"])
        .select_related("customer")
        .prefetch_related("items__product_card__urun", "items__product_card__materials__material")
        .order_by("-created_at", "-id")
    )
    dummy_orders = Order.objects.none()
    start, end, folios, _ = _date_filter(request, folios, dummy_orders)
    rows = [_folio_finance(draft) for draft in folios]

    return render(request, "reports/siparis_finans_foyleri.html", {
        "rows": rows,
        "start": start,
        "end": end,
    })


@login_required
def siparis_finans_foy_detay(request, draft_id):
    if not has_access(request.user, "can_view_reports"):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    draft = get_object_or_404(
        ShowroomDraft.objects
        .select_related("customer")
        .prefetch_related("items__product_card__urun", "items__product_card__materials__material"),
        id=draft_id,
        status__in=["APPROVED", "TRANSFERRED"],
    )
    finance = _folio_finance(draft, include_items=True)
    return render(request, "reports/siparis_finans_foy_detay.html", {
        "draft": draft,
        "finance": finance,
    })
