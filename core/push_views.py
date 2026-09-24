import base64
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from pywebpush import WebPushException, webpush

from .models import ChatMembership, PushSubscription


P256_ORDER = int("FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551", 16)


def _vapid_keys():
    configured_public = getattr(settings, "VAPID_PUBLIC_KEY", "")
    configured_private = getattr(settings, "VAPID_PRIVATE_KEY", "")
    if configured_public and configured_private:
        return configured_public, configured_private
    digest = hashlib.sha256(("moliapp-web-push:" + settings.SECRET_KEY).encode("utf-8")).digest()
    private_value = (int.from_bytes(digest, "big") % (P256_ORDER - 1)) + 1
    key = ec.derive_private_key(private_value, ec.SECP256R1())
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    raw_public = key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    public_b64 = base64.urlsafe_b64encode(raw_public).rstrip(b"=").decode("ascii")
    return public_b64, private_pem


@login_required
@require_GET
def push_config(request):
    public_key, private_key = _vapid_keys()
    return JsonResponse({
        "ok": True,
        "enabled": bool(public_key and private_key),
        "public_key": public_key,
        "subscribed": PushSubscription.objects.filter(user=request.user).exists(),
    })


@login_required
@require_POST
def push_subscribe(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        endpoint = data["endpoint"]
        keys = data["keys"]
        p256dh = keys["p256dh"]
        auth = keys["auth"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "message": "Bildirim kaydı geçersiz."}, status=400)

    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": request.user,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": (request.META.get("HTTP_USER_AGENT") or "")[:500],
        },
    )
    return JsonResponse({"ok": True})


@login_required
@require_POST
def push_unsubscribe(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        endpoint = data.get("endpoint", "")
    except (ValueError, json.JSONDecodeError):
        endpoint = ""
    if endpoint:
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    else:
        PushSubscription.objects.filter(user=request.user).delete()
    return JsonResponse({"ok": True})


def service_worker(request):
    js = r'''self.addEventListener('push', function(event) {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = {body: event.data ? event.data.text() : ''}; }
  const title = data.title || 'MoliApp';
  const options = {
    body: data.body || 'Yeni mesajınız var.',
    icon: '/static/icons/icon-192.png',
    badge: '/static/icons/icon-192.png',
    data: {url: data.url || '/mesajlar/'},
    tag: data.tag || 'moli-message',
    renotify: true
  };
  event.waitUntil(self.registration.showNotification(title, options));
});
self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const target = new URL((event.notification.data && event.notification.data.url) || '/mesajlar/', self.location.origin).href;
  event.waitUntil(clients.matchAll({type:'window', includeUncontrolled:true}).then(function(list) {
    for (const client of list) {
      if ('focus' in client) { client.navigate(target); return client.focus(); }
    }
    if (clients.openWindow) return clients.openWindow(target);
  }));
});'''
    response = HttpResponse(js, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


def send_chat_push(message):
    public_key, private_key = _vapid_keys()
    if not public_key or not private_key:
        return

    sender_name = "MoliApp"
    if message.sender:
        sender_name = message.sender.get_full_name() or message.sender.username
    preview = (message.body or "").strip()
    if not preview:
        preview = "Medya gönderdi" if message.media_url else "Yeni mesaj gönderdi"
    if len(preview) > 140:
        preview = preview[:137] + "..."

    recipient_ids = list(
        ChatMembership.objects.filter(thread=message.thread)
        .exclude(user_id=message.sender_id)
        .values_list("user_id", flat=True)
    )
    if not recipient_ids:
        return

    payload = json.dumps({
        "title": sender_name if message.thread.thread_type == "direct" else (message.thread.name or "MoliApp Grubu"),
        "body": preview,
        "url": f"/mesajlar/{message.thread_id}/",
        "tag": f"moli-chat-{message.thread_id}",
    }, ensure_ascii=False)
    claims = {"sub": getattr(settings, "VAPID_SUBJECT", "mailto:bildirim@moliapp.local")}

    subscriptions = list(PushSubscription.objects.filter(user_id__in=recipient_ids))
    def deliver(sub):
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims=claims,
                timeout=5,
            )
        except WebPushException as exc:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
            body = ""
            try:
                body = (getattr(response, "text", "") or "")[:500]
            except Exception:
                body = ""
            print(
                f"[push] user={sub.user_id} subscription={sub.pk} "
                f"status={status} error={exc} response={body}"
            )
            if status in (404, 410):
                PushSubscription.objects.filter(pk=sub.pk).delete()
        except Exception as exc:
            print(
                f"[push] user={sub.user_id} subscription={sub.pk} "
                f"unexpected_error={type(exc).__name__}: {exc}"
            )

    if subscriptions:
        with ThreadPoolExecutor(max_workers=min(8, len(subscriptions))) as pool:
            list(pool.map(deliver, subscriptions))


def push_test_once(request):
    if request.method != "GET":
        return JsonResponse({"ok": False}, status=405)
    sub = PushSubscription.objects.order_by("-updated_at").first()
    if not sub:
        return JsonResponse({"ok": False, "message": "Abonelik yok."}, status=404)
    public_key, private_key = _vapid_keys()
    try:
        webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=json.dumps({
                "title": "MoliApp",
                "body": "Test bildirimi başarılı 🎉",
                "url": "/mesajlar/",
                "tag": "moli-push-test",
            }, ensure_ascii=False),
            vapid_private_key=private_key,
            vapid_claims={"sub": getattr(settings, "VAPID_SUBJECT", "mailto:bildirim@moliapp.local")},
            timeout=8,
        )
        return JsonResponse({"ok": True})
    except Exception as exc:
        return JsonResponse({"ok": False, "message": str(exc)[:200]}, status=500)


def send_test_push_to_user(user):
    sub = PushSubscription.objects.filter(user=user).order_by("-updated_at").first()
    if not sub:
        return False
    public_key, private_key = _vapid_keys()
    try:
        webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=json.dumps({
                "title": "MoliApp",
                "body": "Test bildirimi başarılı 🎉",
                "url": "/mesajlar/",
                "tag": "moli-push-test",
            }, ensure_ascii=False),
            vapid_private_key=private_key,
            vapid_claims={"sub": getattr(settings, "VAPID_SUBJECT", "mailto:bildirim@moliapp.local")},
            timeout=8,
        )
        return True
    except Exception:
        return False
