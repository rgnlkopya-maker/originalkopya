from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from .models import ShowroomDraft
from .price_list_views import _can_manage
from .showroom_views import _serialize_draft, _draft_summary


def _to_decimal(value):
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


@login_required
def showroom_print_page(request, draft_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    draft = get_object_or_404(
        ShowroomDraft.objects.select_related("customer").prefetch_related("items__product_card__urun"),
        id=draft_id,
        created_by=request.user,
        status__in=["PENDING", "APPROVED"],
    )

    data = _serialize_draft(draft)
    summary = _draft_summary(draft)
    status_label = "Taslak" if draft.status == "PENDING" else "Onaylanan"

    print_items = []
    for item in data["items"]:
        unit_price = _to_decimal(item.get("anlasilan_fiyat"))
        lines = []
        item_total = Decimal("0")
        for row in item.get("satirlar", []):
            try:
                qty = max(1, int(row.get("adet") or 1))
            except (TypeError, ValueError):
                qty = 1
            sizes = row.get("bedenler") or [""]
            for size in sizes:
                line_total = unit_price * qty
                item_total += line_total
                lines.append({
                    "renk": row.get("renk") or "",
                    "beden": size or "",
                    "adet": qty,
                    "aciklama": row.get("aciklama") or "",
                    "unit_price": unit_price,
                    "line_total": line_total,
                })
        print_items.append({
            "urun_kodu": item.get("urun_kodu") or "",
            "unit_price": unit_price,
            "item_total": item_total,
            "lines": lines,
        })

    return render(request, "product_cards/showroom_print.html", {
        "draft": draft,
        "items": print_items,
        "summary": summary,
        "status_label": status_label,
    })
