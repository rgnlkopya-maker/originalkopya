from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from app_settings.access import has_access, order_scope_allows
from .models import Order, OrderFlag


STAGE_GROUPS = {
    "malzeme": {"malzeme_durum"},
    "kesim": {"kesim_durum"},
    "dikim": {"dikim_durum", "dikim_yardim"},
    "fason_dikim": {"dikim_fason_durumu"},
    "nakis": {"nakis_durumu"},
    "susleme": {"susleme_durum", "susleme_yardim"},
    "sevkiyat": {"hazir_durum", "sevkiyat_durum", "konsinye_durum"},
}


def _can_manage_flags(user):
    return has_access(user, "can_edit_orders")


@login_required
@require_POST
def create_order_flag(request, order_id):
    if not _can_manage_flags(request.user):
        return HttpResponseForbidden("Sipariş bayrağı ekleme yetkiniz yok.")
    order = get_object_or_404(Order, pk=order_id)
    if not order_scope_allows(request.user, order):
        return HttpResponseForbidden("Bu siparişe bayrak ekleme yetkiniz yok.")
    note = (request.POST.get("note") or "").strip()
    mode = (request.POST.get("mode") or "TRACK_ALL").strip()
    if mode not in {"TRACK_ALL", "STAGE_ALERT"}:
        mode = "TRACK_ALL"
    stages = [s for s in request.POST.getlist("trigger_stages") if s in STAGE_GROUPS]
    detail_note = (request.POST.get("detail_note") or "").strip()
    if stages and not detail_note:
        return JsonResponse({"ok": False, "error": "Detaylı aşama uyarısı için açıklama yazın."}, status=400)
    if not note:
        return JsonResponse({"ok": False, "error": "Bayrak açıklaması zorunludur."}, status=400)
    if mode == "STAGE_ALERT" and not stages:
        return JsonResponse({"ok": False, "error": "En az bir üretim aşaması seçin."}, status=400)

    flag = OrderFlag.objects.create(
        order=order,
        created_by=request.user,
        note=note,
        mode=mode,
        trigger_stages=stages,
        popup_actor=(mode == "STAGE_ALERT" and request.POST.get("popup_actor") == "1"),
    )
    ids = {int(v) for v in request.POST.getlist("notify_users") if str(v).isdigit()}
    ids.add(request.user.id)
    users = get_user_model().objects.filter(id__in=ids, is_active=True)
    flag.notify_users.set(users)
    detail_ids = {int(v) for v in request.POST.getlist("detail_notify_users") if str(v).isdigit()}
    detail_users = get_user_model().objects.filter(id__in=detail_ids, is_active=True)
    flag.detail_notify_users.set(detail_users)
    return JsonResponse({"ok": True, "flag_id": flag.id})


@login_required
@require_POST
def close_order_flag(request, flag_id):
    flag = get_object_or_404(OrderFlag, pk=flag_id)
    if not _can_manage_flags(request.user):
        return HttpResponseForbidden("Sipariş bayrağını kaldırma yetkiniz yok.")
    flag.is_active = False
    flag.closed_at = timezone.now()
    flag.save(update_fields=["is_active", "closed_at"])
    return JsonResponse({"ok": True})
