import json
import re
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.utils import timezone
from app_settings.access import has_access, data_scope_value
from .assistant_ai import ask_openai, ask_general
from .assistant_shipping_context import build_shipping_context
from .models import AssistantConversation


ACTIVE_KEY = "moli_assistant_active"
LEGACY_KEY = "moli_assistant_threads"
LEGACY_HISTORY_KEY = "moli_assistant_history"


def _migrate_legacy(request):
    if request.session.get("moli_assistant_db_migrated"):
        return
    if not AssistantConversation.objects.filter(user=request.user).exists():
        legacy = request.session.get(LEGACY_KEY, [])
        if not legacy:
            old_messages = request.session.get(LEGACY_HISTORY_KEY, [])
            if old_messages:
                legacy = [{"title": "Önceki konuşma", "messages": old_messages}]
        for item in legacy[:15]:
            messages = item.get("messages", [])
            if not isinstance(messages, list):
                continue
            AssistantConversation.objects.create(user=request.user,
                title=str(item.get("title") or "Önceki konuşma")[:120],
                messages=messages[-30:], mode="moli")
    request.session["moli_assistant_db_migrated"] = True
    request.session.modified = True


def _current(request):
    active = request.session.get(ACTIVE_KEY)
    thread = AssistantConversation.objects.filter(user=request.user, pk=active).first() if str(active).isdigit() else None
    if thread is None:
        thread = AssistantConversation.objects.filter(user=request.user).first()
        if thread:
            request.session[ACTIVE_KEY] = thread.pk
    return thread


def _title(message):
    """Fast deterministic topic title without charging for a second AI request."""
    line = " ".join(message.split())
    line = re.sub(r"^(bana |lütfen |acaba |şimdi |bir |peki )+", "", line, flags=re.I)
    return (line[:65].rstrip(" ,.;:") or "Yeni konuşma")


@login_required
def assistant_page(request):
    if not has_access(request.user, "can_view_assistant"):
        return render(request, "core/asistan.html", {"denied": True})
    _migrate_legacy(request)
    thread = _current(request)
    qs = AssistantConversation.objects.filter(user=request.user)
    search = request.GET.get("q", "").strip()[:80]
    if search:
        qs = qs.filter(title__icontains=search)
    threads = list(qs[:100])
    return render(request, "core/asistan.html", {
        "assistant_history": thread.messages if thread else [],
        "assistant_threads": [{"id": item.pk, "title": item.title, "active": bool(thread and item.pk == thread.pk),
                               "mode": item.mode} for item in threads],
        "active_thread_id": thread.pk if thread else "",
        "active_mode": thread.mode if thread else "moli",
        "search_query": search,
    })


@login_required
@require_POST
def assistant_thread_action(request):
    if not has_access(request.user, "can_view_assistant"):
        return JsonResponse({"ok": False}, status=403)
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False}, status=400)
    action = body.get("action")
    if action == "new":
        mode = body.get("mode", "moli")
        if mode not in ("moli", "general"):
            return JsonResponse({"ok": False, "error": "Geçersiz sohbet türü."}, status=400)
        thread = AssistantConversation.objects.create(user=request.user, mode=mode)
        request.session[ACTIVE_KEY] = thread.pk
    elif action in ("open", "delete"):
        thread = AssistantConversation.objects.filter(user=request.user, pk=body.get("id")).first() if str(body.get("id")).isdigit() else None
        if thread is None:
            return JsonResponse({"ok": False}, status=404)
        if action == "delete":
            was_active = request.session.get(ACTIVE_KEY) == thread.pk
            thread.delete()
            if was_active:
                request.session.pop(ACTIVE_KEY, None)
        else:
            request.session[ACTIVE_KEY] = thread.pk
    else:
        return JsonResponse({"ok": False}, status=400)
    request.session.modified = True
    return JsonResponse({"ok": True})


@login_required
@require_POST
def assistant_api(request):
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
        message = (body.get("message") or "").strip()
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"reply": "Mesaj okunamadı."}, status=400)
    if not message or len(message) > 6000:
        return JsonResponse({"reply": "1-6000 karakter arasında bir mesaj yazın."}, status=400)
    if not has_access(request.user, "can_view_assistant"):
        return JsonResponse({"reply": "Asistan kullanma yetkiniz bulunmuyor."}, status=403)
    _migrate_legacy(request)
    thread = _current(request)
    if thread is None:
        thread = AssistantConversation.objects.create(user=request.user, mode="moli")
        request.session[ACTIVE_KEY] = thread.pk
    history = thread.messages[-12:]
    try:
        if thread.mode == "general":
            reply = ask_general(request.user, message, history)
        else:
            shipping = (build_shipping_context() if has_access(request.user, "can_view_orders")
                        and data_scope_value(request.user, "orders") == "all"
                        else "Sevkiyat kayıtlarına erişim yetkisi yok.")
            enriched = message + "\n\n[SİSTEM SEVKİYAT BAĞLAMI]\n" + shipping
            reply = ask_openai(request.user, enriched, history)
    except Exception as exc:
        return JsonResponse({"reply": "Asistan şu anda yanıt veremiyor: " + str(exc)}, status=503)
    history.extend([{"role": "user", "content": message}, {"role": "assistant", "content": reply}])
    thread.messages = history[-60:]
    if thread.title == "Yeni konuşma":
        thread.title = _title(message)
    thread.save(update_fields=["messages", "title", "updated_at"])
    return JsonResponse({"reply": reply})


@login_required
@require_POST
def assistant_clear(request):
    if not has_access(request.user, "can_view_assistant"):
        return JsonResponse({"ok": False}, status=403)
    thread = _current(request)
    if thread:
        thread.messages = []
        thread.save(update_fields=["messages", "updated_at"])
    return JsonResponse({"ok": True})
