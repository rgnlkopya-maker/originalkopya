from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import ShowroomDraft
from .price_list_views import _can_manage


@login_required
@require_POST
def showroom_change_status(request, draft_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")

    draft = get_object_or_404(
        ShowroomDraft,
        id=draft_id,
        created_by=request.user,
        status__in=["PENDING", "APPROVED", "TRANSFERRED"],
    )

    target_status = (request.POST.get("target_status") or "").strip().upper()
    if target_status not in {"PENDING", "APPROVED"}:
        return HttpResponseBadRequest("Geçersiz durum değişikliği.")

    if draft.status == target_status:
        return redirect("showroom_detail_page", draft_id=draft.id)
    if draft.status == "PENDING" and target_status != "APPROVED":
        return HttpResponseBadRequest("Geçersiz durum değişikliği.")
    if draft.status == "APPROVED" and target_status != "PENDING":
        return HttpResponseBadRequest("Geçersiz durum değişikliği.")

    draft.status = target_status
    draft.save(update_fields=["status", "updated_at"])

    return redirect("showroom_detail_page", draft_id=draft.id)
