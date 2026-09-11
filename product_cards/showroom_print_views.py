from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from .models import ShowroomDraft
from .price_list_views import _can_manage
from .showroom_views import _serialize_draft, _draft_summary


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

    return render(request, "product_cards/showroom_print.html", {
        "draft": draft,
        "items": data["items"],
        "summary": summary,
        "status_label": status_label,
    })
