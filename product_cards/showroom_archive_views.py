from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .models import ShowroomDraft
from .price_list_views import _can_manage
from .showroom_views import _draft_summary, _payment_rows, _serialize_draft


@login_required
@require_GET
def showroom_archive_list(request):
    if not _can_manage(request.user):
        return JsonResponse({"ok": False, "message": "Yetkiniz yok."}, status=403)

    kind = request.GET.get("kind")
    if kind == "draft":
        statuses = ["PENDING"]
    elif kind == "approved":
        statuses = ["APPROVED", "TRANSFERRED"]
    else:
        return JsonResponse({"ok": False, "message": "Liste türü geçersiz."}, status=400)

    drafts = (
        ShowroomDraft.objects.filter(created_by=request.user, status__in=statuses)
        .select_related("customer")
        .prefetch_related("items", "payments")
        .order_by("-updated_at", "-id")
    )
    return JsonResponse({"ok": True, "kind": kind, "items": [_draft_summary(d) for d in drafts]})


@login_required
def showroom_detail_page(request, draft_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    draft = get_object_or_404(
        ShowroomDraft.objects.select_related("customer").prefetch_related(
            "items__product_card__urun", "payments"
        ),
        id=draft_id,
        created_by=request.user,
        status__in=["PENDING", "APPROVED", "TRANSFERRED"],
    )
    data = _serialize_draft(draft)
    summary = _draft_summary(draft)
    if draft.status == "PENDING":
        status_label = "Taslak"
        back_url_name = "showroom_drafts_page"
    elif draft.status == "TRANSFERRED":
        status_label = "Siparişe Dönüştürüldü"
        back_url_name = "showroom_approved_page"
    else:
        status_label = "Onaylanan"
        back_url_name = "showroom_approved_page"

    return render(request, "product_cards/showroom_detail.html", {
        "draft": draft,
        "items": data["items"],
        "summary": summary,
        "payments": _payment_rows(draft),
        "status_label": status_label,
        "back_url_name": back_url_name,
    })
