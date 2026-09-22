from app_settings.access import has_feature_access
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Order, ProductCost, URUN_TIPI_CHOICES
from .models import ShowroomDraft, ShowroomOrderLink
from .price_list_views import _can_manage
from .showroom_views import CUSTOMER_BASE_PRICE_SIZE, _apply_pricing_operations


def _transfer_pricing(draft, rows):
    """Kontrol ekranı ve gerçek siparişlerde KDV hariç fiyat + ayrı KDV oranı kullanılır."""
    subtotal = sum(
        (Decimal(row["birim_fiyat"] or 0) * Decimal(row["adet"] or 1) for row in rows),
        Decimal("0"),
    )

    pricing_ops = draft.pricing_operations or []
    if pricing_ops or draft.folio_adjustment_target is not None:
        pricing_result = _apply_pricing_operations(
            subtotal, pricing_ops, draft.folio_adjustment_target
        )
        gross_target_total = pricing_result["folio_total"]

        vat_multiplier = Decimal("1")
        for step in pricing_result["steps"]:
            if step["type"] == "VAT":
                vat_multiplier *= Decimal("1") + (Decimal(step["value"]) / Decimal("100"))

        vat_rate_for_order = (
            (vat_multiplier - Decimal("1")) * Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        net_target_total = (
            gross_target_total / vat_multiplier
            if vat_multiplier > 0
            else gross_target_total
        )
    else:
        discount = (
            subtotal * Decimal(draft.discount_rate or 0) / Decimal("100")
            if draft.discount_rate and draft.discount_rate > 0
            else Decimal(draft.overall_discount_amount or 0)
        )
        discount = min(subtotal, max(Decimal("0"), discount))
        taxable = max(Decimal("0"), subtotal - discount)
        vat_rate_for_order = max(
            Decimal("0"),
            min(Decimal("100"), Decimal(draft.vat_rate or 0)),
        )
        vat_multiplier = Decimal("1") + (vat_rate_for_order / Decimal("100"))
        gross_target_total = taxable * vat_multiplier
        net_target_total = taxable

    net_factor = (net_target_total / subtotal) if subtotal > 0 else Decimal("0")

    unit_orders = []
    for row_index, row in enumerate(rows):
        for _ in range(row["adet"]):
            unit_orders.append((row_index, row))

    allocated_prices = []
    allocated_total = Decimal("0")
    for index, (row_index, row) in enumerate(unit_orders):
        if index == len(unit_orders) - 1:
            final_price = max(Decimal("0"), net_target_total - allocated_total)
        else:
            final_price = (
                Decimal(row["birim_fiyat"] or 0) * net_factor
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            allocated_total += final_price
        allocated_prices.append(
            (row_index, final_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        )

    priced_rows = []
    by_row = {}
    for row_index, price in allocated_prices:
        by_row.setdefault(row_index, []).append(price)

    for row_index, row in enumerate(rows):
        row_copy = dict(row)
        prices = by_row.get(row_index, [])
        row_total = sum(prices, Decimal("0"))
        if prices:
            if all(p == prices[0] for p in prices):
                display_unit = prices[0]
            else:
                display_unit = (row_total / Decimal(len(prices))).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
        else:
            display_unit = Decimal("0")
        row_copy["birim_fiyat"] = display_unit
        row_copy["satir_toplami"] = row_total
        row_copy["kdv_orani"] = vat_rate_for_order
        row_copy["_allocated_prices"] = prices
        priced_rows.append(row_copy)

    return (
        priced_rows,
        net_target_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        vat_rate_for_order,
    )

def _draft_rows(draft):
    type_labels = dict(URUN_TIPI_CHOICES)
    rows = []
    total_orders = 0
    total_value = Decimal("0")
    product_codes = set()

    for item in draft.items.select_related("product_card__urun").order_by(
        "product_card__urun__kod", "color", "size", "id"
    ):
        qty = max(1, int(item.quantity or 1))
        unit_price = item.unit_price or Decimal("0")
        row_total = unit_price * qty
        urun = item.product_card.urun
        urun_tipi = getattr(urun, "urun_tipi", "") or ""
        rows.append({
            "draft_item_id": item.id,
            "urun_kodu": urun.kod,
            "urun_tipi": urun_tipi,
            "urun_tipi_label": type_labels.get(urun_tipi, urun_tipi or "—"),
            "renk": item.color or "",
            "beden": item.size or "",
            "adet": qty,
            "aciklama": item.description or "",
            "birim_fiyat": unit_price,
            "satir_toplami": row_total,
        })
        total_orders += qty
        total_value += row_total
        product_codes.add(urun.kod)
    return rows, total_orders, total_value, len(product_codes)


@login_required
def showroom_transfer_preview(request, draft_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    draft = get_object_or_404(
        ShowroomDraft.objects.select_related("customer").prefetch_related("items__product_card__urun"),
        id=draft_id,
        created_by=request.user,
        status="APPROVED",
    )
    rows, total_orders, _, product_count = _draft_rows(draft)
    rows, total_value, _ = _transfer_pricing(draft, rows)
    warnings = []
    if not draft.customer_id:
        warnings.append("Bu Föyde müşteri seçilmemiş. Siparişe aktarmadan önce müşteri seçilmesi gerekir.")
    if not rows:
        warnings.append("Bu Föyde siparişe dönüştürülecek ürün satırı bulunmuyor.")
    has_base_price_rows = any(row["beden"] == CUSTOMER_BASE_PRICE_SIZE for row in rows)
    if has_base_price_rows:
        warnings.append(
            "Baz fiyat (bedensiz) satırları doğrudan siparişe aktarılamaz. "
            "Gerçek siparişi girerken her satırın basen ölçüsünü yazın."
        )

    return render(request, "product_cards/showroom_transfer_preview.html", {
        "draft": draft,
        "rows": rows,
        "total_orders": total_orders,
        "product_count": product_count,
        "total_value": total_value,
        "warnings": warnings,
        "can_transfer": bool(draft.customer_id and rows and not has_base_price_rows),
        "order_type_label": dict(Order.SIPARIS_TIPLERI).get(draft.order_type or "SERI", draft.order_type or "SERI"),
    })


@login_required
@transaction.atomic
def showroom_transfer_create(request, draft_id):
    if request.method != "POST":
        return redirect("showroom_transfer_preview", draft_id=draft_id)
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")

    # Yalnızca Föy satırını kilitle. Nullable customer FK'yi aynı SELECT FOR UPDATE
    # sorgusuna katmak PostgreSQL'de outer join kilit hatasına yol açabilir.
    draft = get_object_or_404(
        ShowroomDraft.objects.select_for_update(),
        id=draft_id,
        created_by=request.user,
    )
    if draft.status == "TRANSFERRED":
        messages.warning(request, "Bu Föy daha önce siparişe aktarılmış.")
        return redirect("order_list")
    if draft.status != "APPROVED":
        messages.warning(request, "Yalnızca onaylanan Föyler siparişe aktarılabilir.")
        return redirect("showroom_approved_page")
    if draft.orders_created:
        messages.warning(request, "Bu Föyden daha önce siparişler oluşturulmuş.")
        return redirect("showroom_detail_page", draft_id=draft.id)
    if not draft.customer_id:
        messages.error(request, "Sipariş oluşturmak için Föyde müşteri seçilmiş olmalıdır.")
        return redirect("showroom_transfer_preview", draft_id=draft.id)

    rows, total_orders, _, _ = _draft_rows(draft)
    if not rows:
        messages.error(request, "Siparişe dönüştürülecek ürün bulunamadı.")
        return redirect("showroom_transfer_preview", draft_id=draft.id)
    if any(row["beden"] == CUSTOMER_BASE_PRICE_SIZE for row in rows):
        messages.error(
            request,
            "Baz fiyat (bedensiz) satırları siparişe aktarılamaz. "
            "Siparişleri basen ölçülerini girerek oluşturun.",
        )
        return redirect("showroom_transfer_preview", draft_id=draft.id)

    order_type = draft.order_type or "SERI"
    if order_type == "KONSINYE" and not has_feature_access(request.user, "consignment.create_production"):
        messages.error(request, "Bu Föyü KONSİNYE siparişine dönüştürme yetkiniz yok.")
        return redirect("showroom_transfer_preview", draft_id=draft.id)

    customer = draft.customer
    cost_cache = {}
    created = 0

    rows, _, vat_rate_for_order = _transfer_pricing(draft, rows)

    for row in rows:
        code = row["urun_kodu"]
        if code not in cost_cache:
            pcost = ProductCost.objects.filter(urun_kodu__iexact=code).first()
            cost_cache[code] = (
                (pcost.maliyet or Decimal("0")) if pcost else Decimal("0"),
                (pcost.para_birimi or "TRY") if pcost else "TRY",
            )
        cost, cost_currency = cost_cache[code]
        for final_price in row.get("_allocated_prices", []):
            order = Order.objects.create(
                siparis_tipi=order_type,
                musteri=customer,
                urun_kodu=code,
                urun_tipi=row["urun_tipi"],
                renk=row["renk"] or None,
                beden=row["beden"] or None,
                adet=1,
                aciklama=row["aciklama"] or None,
                satis_fiyati=final_price,
                vat_rate=vat_rate_for_order,
                para_birimi=draft.currency or "TRY",
                maliyet_uygulanan=cost,
                maliyet_para_birimi=cost_currency,
            )
            ShowroomOrderLink.objects.create(
                draft=draft,
                draft_item_id=row.get("draft_item_id"),
                order=order,
            )
            created += 1

    if created != total_orders:
        raise RuntimeError("Föy sipariş adetleri ile oluşturulan sipariş adetleri eşleşmedi.")

    draft.status = "TRANSFERRED"
    draft.orders_created = True
    draft.save(update_fields=["status", "orders_created", "updated_at"])
    messages.success(request, f"Föyden {created} adet sipariş başarıyla oluşturuldu.")
    return redirect("order_list")
