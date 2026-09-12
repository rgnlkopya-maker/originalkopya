from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from core.models import URUN_TIPI_CHOICES
from .models import ShowroomDraft
from .price_list_views import _can_manage


@login_required
def showroom_transfer_preview(request, draft_id):
    """Onaylanan Föyden oluşacak Order kayıtlarını yalnızca önizler.

    Bu aşamada veritabanında Order kaydı oluşturulmaz ve Föy durumu değiştirilmez.
    """
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    draft = get_object_or_404(
        ShowroomDraft.objects.select_related("customer").prefetch_related(
            "items__product_card__urun"
        ),
        id=draft_id,
        created_by=request.user,
        status="APPROVED",
    )

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

    warnings = []
    if not draft.customer_id:
        warnings.append("Bu Föyde müşteri seçilmemiş. Siparişe aktarmadan önce müşteri seçilmesi gerekir.")
    if not rows:
        warnings.append("Bu Föyde siparişe dönüştürülecek ürün satırı bulunmuyor.")

    return render(request, "product_cards/showroom_transfer_preview.html", {
        "draft": draft,
        "rows": rows,
        "total_orders": total_orders,
        "product_count": len(product_codes),
        "total_value": total_value,
        "warnings": warnings,
    })
