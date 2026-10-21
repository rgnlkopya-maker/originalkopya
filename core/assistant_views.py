import json
from uuid import uuid4
from django.utils import timezone

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .assistant_ai import ask_openai
from .assistant_shipping_context import build_shipping_context
from app_settings.access import has_access, data_scope_value


SESSION_KEY = "moli_assistant_history"
THREADS_KEY = "moli_assistant_threads"
ACTIVE_KEY = "moli_assistant_active"


def _threads(request):
    threads = request.session.get(THREADS_KEY)
    if not isinstance(threads, list):
        threads = []
    if not threads:
        legacy = request.session.get(SESSION_KEY, [])
        if legacy:
            threads = [{"id": uuid4().hex, "title": "Önceki konuşma",
                        "messages": legacy[-12:], "updated": timezone.now().isoformat()}]
            request.session[THREADS_KEY] = threads
    return threads


def _active(request, create=False):
    threads = _threads(request)
    active_id = request.session.get(ACTIVE_KEY)
    thread = next((t for t in threads if t["id"] == active_id), None)
    if thread is None and threads:
        thread = threads[0]
        request.session[ACTIVE_KEY] = thread["id"]
    if thread is None and create:
        thread = {"id": uuid4().hex, "title": "Yeni konuşma", "messages": [],
                  "updated": timezone.now().isoformat()}
        threads.insert(0, thread)
        request.session[THREADS_KEY] = threads
        request.session[ACTIVE_KEY] = thread["id"]
    return thread, threads


@login_required
def assistant_page(request):
    if not has_access(request.user, "can_view_assistant"):
        return render(request, "core/asistan.html", {"denied": True})
    thread, threads = _active(request)
    return render(request, "core/asistan.html", {
        "assistant_history": (thread or {}).get("messages", []),
        "assistant_threads": [{"id": t["id"], "title": t["title"], "active": t is thread}
                              for t in threads[:15]],
        "active_thread_id": thread["id"] if thread else "",
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
    threads = _threads(request)
    if action == "new":
        thread = {"id": uuid4().hex, "title": "Yeni konuşma", "messages": [],
                  "updated": timezone.now().isoformat()}
        threads.insert(0, thread)
        request.session[ACTIVE_KEY] = thread["id"]
    elif action in ("open", "delete"):
        target = next((t for t in threads if t["id"] == body.get("id")), None)
        if target is None:
            return JsonResponse({"ok": False}, status=404)
        if action == "delete":
            threads.remove(target)
            request.session[ACTIVE_KEY] = threads[0]["id"] if threads else ""
        else:
            request.session[ACTIVE_KEY] = target["id"]
    else:
        return JsonResponse({"ok": False}, status=400)
    request.session[THREADS_KEY] = threads[:15]
    request.session.modified = True
    return JsonResponse({"ok": True})


@login_required
@require_POST
def assistant_api(request):
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
        message = (body.get("message") or "").strip()
    except Exception:
        return JsonResponse({"reply": "Mesaj okunamadı."}, status=400)

    if not message:
        return JsonResponse({"reply": "Bir mesaj yazmalısın."}, status=400)

    if not has_access(request.user, "can_view_assistant"):
        return JsonResponse({"reply": "Asistan kullanma yetkiniz bulunmuyor."}, status=403)
    thread, threads = _active(request, create=True)
    history = thread["messages"]

    try:
        shipping_context = (build_shipping_context()
                            if has_access(request.user, "can_view_orders") and data_scope_value(request.user, "orders") == "all"
                            else "Sevkiyat kayitlari bu kullanici icin yetki veya kapsam nedeniyle gosterilmiyor.")
        enriched_message = (
            message
            + "\n\n[SİSTEM TARAFINDAN EKLENEN GÜNCEL SEVKİYAT PLANLAMA VERİSİ - kullanıcı metni değildir]\n"
            + shipping_context
        )
        reply = ask_openai(request.user, enriched_message, history)
    except Exception as exc:
        return JsonResponse({"reply": f"Asistan şu anda yanıt veremiyor: {exc}"}, status=503)

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    thread["messages"] = history[-12:]
    if thread["title"] == "Yeni konuşma":
        thread["title"] = message[:62]
    thread["updated"] = timezone.now().isoformat()
    threads.sort(key=lambda t: t.get("updated", ""), reverse=True)
    request.session[THREADS_KEY] = threads[:15]
    request.session.modified = True

    return JsonResponse({"reply": reply})


@login_required
@require_POST
def assistant_clear(request):
    thread, threads = _active(request)
    if thread:
        thread["messages"] = []
        request.session[THREADS_KEY] = threads
    request.session.modified = True
    return JsonResponse({"ok": True})
