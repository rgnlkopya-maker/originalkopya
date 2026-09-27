import hashlib
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from app_settings.access import order_scope_allows
from .models import Order, OrderEvent, OrderNoticeRead


CHANGE_LABELS = {
    "urun_kodu": "Ürün Kodu",
    "renk": "Renk",
    "beden": "Beden",
    "adet": "Adet",
    "teslim_tarihi": "Teslim Tarihi",
    "aciklama": "Açıklama",
    "musteri_referans": "Müşteri Referansı",
}


def _clean(value):
    if value in (None, "", "None"):
        return ""
    return str(value).strip()


def _display(stage, value):
    if value in (None, "", "None"):
        return "—"
    value = str(value)
    if stage == "teslim_tarihi":
        try:
            from datetime import date
            return date.fromisoformat(value[:10]).strftime("%d.%m.%Y")
        except (TypeError, ValueError):
            pass
    return value


def build_order_notice(order):
    events = list(
        OrderEvent.objects.filter(
            order=order,
            event_type="order_update",
            stage__in=CHANGE_LABELS.keys(),
        ).order_by("-timestamp", "-id")
    )
    changes = []
    for event in events:
        if _clean(event.old_value) == _clean(event.new_value):
            continue
        changes.append({
            "id": event.id,
            "field": CHANGE_LABELS.get(event.stage, event.stage),
            "old": _display(event.stage, event.old_value),
            "new": _display(event.stage, event.new_value),
            "user": event.user or "-",
            "timestamp": event.timestamp.strftime("%d.%m.%Y %H:%M"),
        })

    description = (order.aciklama or "").strip()
    hash_source = {
        "description": description,
        "changes": [
            {
                "id": c["id"],
                "field": c["field"],
                "old": c["old"],
                "new": c["new"],
            }
            for c in changes
        ],
    }
    notice_hash = hashlib.sha256(
        json.dumps(hash_source, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    return {
        "description": description,
        "changes": changes,
        "notice_hash": notice_hash,
        "has_notice": bool(description or changes),
    }


@login_required
@require_http_methods(["GET", "POST"])
def order_notice(request, order_id):
    order = get_object_or_404(Order.objects.select_related("musteri"), pk=order_id)
    if not order_scope_allows(request.user, order):
        return HttpResponseForbidden("Bu siparişi görme yetkiniz yok.")

    notice = build_order_notice(order)
    current_hash = notice["notice_hash"]

    if request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            body = {}
        posted_hash = body.get("notice_hash")
        if posted_hash != current_hash:
            return JsonResponse(
                {"ok": False, "changed": True, "message": "Uyarı içeriği değişti. Lütfen yeniden okuyun."},
                status=409,
            )
        if notice["has_notice"]:
            OrderNoticeRead.objects.update_or_create(
                user=request.user,
                order=order,
                defaults={"notice_hash": current_hash},
            )
        return JsonResponse({"ok": True, "notice_hash": current_hash})

    receipt = OrderNoticeRead.objects.filter(user=request.user, order=order).first()
    is_read = bool(receipt and receipt.notice_hash == current_hash)
    payload = {
        "ok": True,
        "order_id": order.id,
        "order_number": order.siparis_numarasi,
        "customer": str(order.musteri) if order.musteri_id else "",
        "description": notice["description"],
        "changes": notice["changes"],
        "notice_hash": current_hash,
        "has_notice": notice["has_notice"],
        "is_read": is_read,
    }

    is_manager = request.user.is_superuser or request.user.groups.filter(name__in=["patron", "mudur"]).exists()
    if is_manager and notice["has_notice"]:
        User = get_user_model()
        active_users = User.objects.filter(is_active=True).order_by("first_name", "username")
        valid_reads = {
            r.user_id: r.read_at
            for r in OrderNoticeRead.objects.filter(order=order, notice_hash=current_hash).select_related("user")
        }
        payload["read_status"] = [
            {
                "user": (u.get_full_name() or u.username),
                "read": u.id in valid_reads,
                "read_at": valid_reads[u.id].strftime("%d.%m.%Y %H:%M") if u.id in valid_reads else "",
            }
            for u in active_users
        ]

    return JsonResponse(payload)
