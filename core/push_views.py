import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from pywebpush import WebPushException, webpush

from .models import ChatMembership, PushSubscription


@login_required
@require_GET
def push_config(request):
    return JsonResponse({
        "ok": True,
        "enabled": bool(getattr(settings, "VAPID_PUBLIC_KEY", "")),
        "public_key": getattr(settings, "VAPID_PUBLIC_KEY", ""),
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
    public_key = getattr(settings, "VAPID_PUBLIC_KEY", "")
    private_key = getattr(settings, "VAPID_PRIVATE_KEY", "")
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

    for sub in PushSubscription.objects.filter(user_id__in=recipient_ids):
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
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                sub.delete()
        except Exception:
            continue
