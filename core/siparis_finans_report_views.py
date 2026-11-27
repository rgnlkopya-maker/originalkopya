import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from app_settings.access import has_access
from core.models import Order
from product_cards.models import ExchangeRate, ShowroomDraft
from product_cards.showroom_views import _apply_pricing_operations


logger = logging.getLogger(__name__)
MONEY = Decimal("0.01")


def _q(value):
    return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)


RATE_FIELDS = {"USD": "usd_try", "EUR": "eur_try", "GBP": "gbp_try"}
MAX_RATE_AGE = timedelta(days=7)


def _historical_rate(currency, rate_day, cache):
    field = RATE_FIELDS.get(currency)
    if field is None or rate_day is None:
        return None, None
    key = (currency, rate_day)
    if key not in cache:
        cache[key] = (
            ExchangeRate.objects.filter(
                rate_date__range=(rate_day - MAX_RATE_AGE, rate_day),
                **{f"{field}__gt": 1},
            ).order_by("-rate_date").values_list(field, "rate_date").first()
            or (None, None)
        )
    return cache[key]


def _folio_sale_rate(draft, currency, cache):
    if currency == "TRY":
        return Decimal("1"), "", None
    field = RATE_FIELDS.get(currency)
    saved = getattr(draft, field, None) if field else None
    if saved is not None and saved > 1:
        return saved, "Föy kuru", None
    rate, rate_day = _historical_rate(currency, timezone.localdate(draft.created_at), cache)
    return rate, "TCMB arşiv kuru", rate_day


def _linked_cost_try(order, cache):
    amount = Decimal(order.toplam_maliyet or 0)
    currency = order.maliyet_para_birimi or "TRY"
    if currency == "TRY" or amount == 0:
        return amount
    rate, _ = _historical_rate(currency, order.siparis_tarihi, cache)
    return amount * rate if rate is not None else None


def _folio_finance(draft, include_items=False, rate_cache=None):
    rate_cache = {} if rate_cache is None else rate_cache
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
    currency = (draft.currency or "TRY").upper()
    rate, rate_source, rate_day = _folio_sale_rate(draft, currency, rate_cache)
    pending_review = bool(draft.import_pending_items)
    revenue_missing = rate is None and bool(net_total or gross_total)
    net_total_try = None if revenue_missing else net_total * (rate or 1)
    gross_total_try = None if revenue_missing else gross_total * (rate or 1)

    linked_orders_by_item = {}
    if draft.status == "TRANSFERRED":
        for link in draft.order_links.select_related("order").all():
            if link.draft_item_id:
                linked_orders_by_item.setdefault(link.draft_item_id, []).append(link.order)

    total_cost = Decimal("0")
    cost_missing = False
    missing_sale_price = False
    missing_product_cost = False
    product_count = set()
    total_qty = 0
    detail_items = []

    for item in items:
        qty = max(1, int(item.quantity or 1))
        total_qty += qty
        code = item.product_card.urun.kod
        product_count.add(code)

        unit_price = Decimal(item.unit_price or 0)
        missing_sale_price |= unit_price <= 0
        net_unit_native = unit_price * net_factor
        net_unit = None if revenue_missing else net_unit_native * (rate or 1)
        linked_orders = linked_orders_by_item.get(item.id, [])
        valid_linked_orders = [order for order in linked_orders if order is not None]
        if len(valid_linked_orders) != len(linked_orders):
            logger.warning(
                "[SIPARIS_FINANS] Missing linked order draft_id=%s draft_item_id=%s missing_count=%s",
                draft.pk, item.pk, len(linked_orders) - len(valid_linked_orders),
            )
        if valid_linked_orders:
            linked_costs = [(_linked_cost_try(order, rate_cache), order.adet or 1)
                            for order in valid_linked_orders]
            missing_product_cost |= any(cost is not None and cost <= 0 for cost, _ in linked_costs)
            # A partly transferred row still has units that depend on the product card.
            if sum(count for _, count in linked_costs) < qty:
                missing_product_cost |= Decimal(item.product_card.toplam_maliyet or 0) <= 0
            row_cost = (None if any(cost is None for cost, _ in linked_costs) else
                        sum((cost * count for cost, count in linked_costs), Decimal("0")))
        else:
            # Ürün kartı maliyeti zaten TL; satış kuruyla tekrar çarpmayın.
            card_cost = Decimal(item.product_card.toplam_maliyet or 0)
            missing_product_cost |= card_cost <= 0
            row_cost = card_cost * qty

        unit_cost = row_cost / qty if row_cost is not None else None
        row_revenue = net_unit * qty if net_unit is not None else None
        unit_profit = net_unit - unit_cost if net_unit is not None and unit_cost is not None else None
        unit_profit_rate = (unit_profit / net_unit * 100
                            if unit_profit is not None and net_unit > 0 else None)
        if row_cost is None:
            cost_missing = True
        else:
            total_cost += row_cost

        if include_items:
            detail_items.append({
                "code": code,
                "color": item.color or "—",
                "size": item.size or "—",
                "quantity": qty,
                "description": item.description or "—",
                "net_unit_price": _q(net_unit) if net_unit is not None else None,
                "unit_cost": _q(unit_cost) if unit_cost is not None else None,
                "unit_profit": _q(unit_profit) if unit_profit is not None else None,
                "unit_profit_rate": _q(unit_profit_rate) if unit_profit_rate is not None else None,
                "row_revenue": row_revenue,
                "row_cost": row_cost,
            })

    if cost_missing:
        total_cost = None
    total_profit = (net_total_try - total_cost
                    if net_total_try is not None and total_cost is not None else None)
    profit_rate = (total_profit / net_total_try * 100
                   if total_profit is not None and net_total_try > 0 else None)

    return {
        "id": draft.id,
        "customer": draft.customer.ad if draft.customer else "Müşteri seçilmedi",
        "date": draft.created_at,
        "updated_at": draft.updated_at,
        "product_count": len(product_count),
        "total_qty": total_qty,
        "revenue": _q(net_total_try) if net_total_try is not None and not pending_review else None,
        "gross_total": _q(gross_total_try) if gross_total_try is not None and not pending_review else None,
        "cost": _q(total_cost) if total_cost is not None and not pending_review else None,
        "profit": _q(total_profit) if total_profit is not None and not pending_review else None,
        "profit_rate": _q(profit_rate) if profit_rate is not None and not pending_review else None,
        "currency": currency,
        "native_revenue": _q(net_total),
        "rate": rate,
        "rate_source": rate_source,
        "rate_day": rate_day,
        "revenue_missing": revenue_missing,
        "cost_missing": cost_missing,
        "missing_sale_price": missing_sale_price,
        "missing_product_cost": missing_product_cost,
        "pending_review": pending_review,
        "items": detail_items,
    }


def _folio_finance_logged(draft, include_items=False, rate_cache=None):
    try:
        return _folio_finance(draft, include_items=include_items, rate_cache=rate_cache)
    except Exception:
        logger.exception(
            "[SIPARIS_FINANS] Folio calculation failed draft_id=%s status=%s include_items=%s",
            draft.pk, draft.status, include_items,
        )
        raise


def _order_type_summary(qs):
    revenue = Decimal("0")
    cost = Decimal("0")
    product_codes = set()
    total_qty = 0
    order_count = 0
    for order in qs:
        order_count += 1
        if (order.urun_kodu or "").strip():
            product_codes.add(order.urun_kodu.strip().casefold())
        total_qty += int(order.adet or 1)
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
        "count": order_count,
        "product_count": len(product_codes),
        "total_qty": total_qty,
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
    orders = Order.objects.filter(is_active=True).exclude(siparis_tipi="MALZEME").select_related("musteri")
    start, end, folios, orders = _date_filter(request, folios, orders)

    folio_rows = []
    model_totals = {}
    rate_cache = {}
    missing_rates = pending_folios = 0
    for draft in folios:
        finance = _folio_finance_logged(draft, include_items=True, rate_cache=rate_cache)
        if finance["pending_review"]:
            pending_folios += 1
            continue
        if finance["revenue_missing"]:
            missing_rates += 1
            continue
        folio_rows.append(finance)
        for item in finance["items"]:
            code = item["code"]
            row = model_totals.setdefault(code, {"code": code, "quantity": 0, "revenue": Decimal("0"), "cost": Decimal("0")})
            row["quantity"] += item["quantity"]
            row["revenue"] += item["row_revenue"]
            if item["row_cost"] is None:
                row["cost"] = None
            elif row["cost"] is not None:
                row["cost"] += item["row_cost"]
    model_rows = []
    for row in model_totals.values():
        qty, revenue, cost = row["quantity"], row["revenue"], row["cost"]
        profit = revenue - cost if cost is not None else None
        model_rows.append({
            "code": row["code"], "quantity": qty, "revenue": _q(revenue),
            "cost": _q(cost) if cost is not None else None,
            "profit": _q(profit) if profit is not None else None,
            "unit_price": _q(revenue / qty),
            "unit_cost": _q(cost / qty) if cost is not None else None,
            "profit_rate": _q(profit / revenue * 100) if profit is not None and revenue > 0 else None,
        })
    model_rows.sort(key=lambda row: (-row["revenue"], row["code"]))

    folio_revenue = sum((x["revenue"] for x in folio_rows), Decimal("0"))
    folio_cost = (None if any(x["cost_missing"] for x in folio_rows)
                  else sum((x["cost"] for x in folio_rows), Decimal("0")))
    folio_profit = folio_revenue - folio_cost if folio_cost is not None else None
    folio_rate = (folio_profit / folio_revenue * 100
                  if folio_profit is not None and folio_revenue > 0 else None)

    context = {
        "start": start,
        "end": end,
        "model_rows": model_rows,
        "pending_folios": pending_folios,
        "missing_folio_rates": missing_rates,
        "folio_summary": {
            "revenue": _q(folio_revenue),
            "cost": _q(folio_cost) if folio_cost is not None else None,
            "profit": _q(folio_profit) if folio_profit is not None else None,
            "profit_rate": _q(folio_rate) if folio_rate is not None else None,
            "count": len(folio_rows),
            "product_count": sum(row["product_count"] for row in folio_rows),
            "total_qty": sum(row["total_qty"] for row in folio_rows),
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
    rate_cache = {}
    rows = [_folio_finance_logged(draft, rate_cache=rate_cache) for draft in folios]

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
    finance = _folio_finance_logged(draft, include_items=True)
    return render(request, "reports/siparis_finans_foy_detay.html", {
        "draft": draft,
        "finance": finance,
    })
