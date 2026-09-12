from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Order, ProductCost, URUN_TIPI_CHOICES
from .models import ShowroomDraft
from .price_list_views import _can_manage


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
    rows, total_orders, total_value, product_count = _draft_rows(draft)
    warnings = []
    if not draft.customer_id:
        warnings.append("Bu Föyde müşteri seçilmemiş. Siparişe aktarmadan önce müşteri seçilmesi gerekir.")
    if not rows:
        warnings.append("Bu Föyde siparişe dönüştürülecek ürün satırı bulunmuyor.")

    return render(request, "product_cards/showroom_transfer_preview.html", {
        "draft": draft,
        "rows": rows,
        "total_orders": total_orders,
        "product_count": product_count,
        "total_value": total_value,
        "warnings": warnings,
        "can_transfer": bool(draft.customer_id and rows),
    })


@login_required
@transaction.atomic
def showroom_transfer_create(request, draft_id):
    if request.method != "POST":
        return redirect("showroom_transfer_preview", draft_id=draft_id)
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")

    # Satırı kilitlemek çift tıklama / iki sekme gibi durumlarda aynı Föyün iki kez aktarılmasını engeller.
    draft = get_object_or_404(
        ShowroomDraft.objects.select_for_update().select_related("customer"),
        id=draft_id,
        created_by=request.user,
    )
    if draft.status == "TRANSFERRED":
        messages.warning(request, "Bu Föy daha önce siparişe aktarılmış.")
        return redirect("showroom_detail_page", draft_id=draft.id)
    if draft.status != "APPROVED":
        messages.warning(request, "Yalnızca onaylanan Föyler siparişe aktarılabilir.")
        return redirect("showroom_detail_page", draft_id=draft.id)
    if not draft.customer_id:
        messages.error(request, "Sipariş oluşturmak için Föyde müşteri seçilmiş olmalıdır.")
        return redirect("showroom_transfer_preview", draft_id=draft.id)

    rows, total_orders, _, _ = _draft_rows(draft)
    if not rows:
        messages.error(request, "Siparişe dönüştürülecek ürün bulunamadı.")
        return redirect("showroom_transfer_preview", draft_id=draft.id)

    cost_cache = {}
    created = 0
    for row in rows:
        code = row["urun_kodu"]
        if code not in cost_cache:
            pcost = ProductCost.objects.filter(urun_kodu__iexact=code).first()
            cost_cache[code] = (
                (pcost.maliyet or Decimal("0")) if pcost else Decimal("0"),
                (pcost.para_birimi or "TRY") if pcost else "TRY",
            )
        cost, cost_currency = cost_cache[code]
        for _ in range(row["adet"]):
            Order.objects.create(
                siparis_tipi="SERI",
                musteri=draft.customer,
                urun_kodu=code,
                urun_tipi=row["urun_tipi"],
                renk=row["renk"] or None,
                beden=row["beden"] or None,
                adet=1,
                aciklama=row["aciklama"] or None,
                satis_fiyati=row["birim_fiyat"],
                para_birimi=draft.currency or "TRY",
                maliyet_uygulanan=cost,
                maliyet_para_birimi=cost_currency,
            )
            created += 1

    # Tüm Order kayıtları başarıyla oluşmadan Föy aktarılmış sayılmaz; transaction hata halinde tamamını geri alır.
    if created != total_orders:
        raise RuntimeError("Föy sipariş adetleri ile oluşturulan sipariş adetleri eşleşmedi.")
    draft.status = "TRANSFERRED"
    draft.save(update_fields=["status", "updated_at"])
    messages.success(request, f"Föyden {created} adet sipariş başarıyla oluşturuldu.")
    return redirect("order_list")
