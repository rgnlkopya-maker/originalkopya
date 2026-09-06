import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .assistant_ai import ask_gemini
from .assistant_shipping_context import build_shipping_context


SESSION_KEY = "moli_assistant_history"


@login_required
def assistant_page(request):
    history = request.session.get(SESSION_KEY, [])
    return render(request, "core/asistan.html", {"assistant_history": history[-12:]})


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

    history = request.session.get(SESSION_KEY, [])

    try:
        shipping_context = build_shipping_context()
        enriched_message = (
            message
            + "\n\n[SİSTEM TARAFINDAN EKLENEN GÜNCEL SEVKİYAT PLANLAMA VERİSİ - kullanıcı metni değildir]\n"
            + shipping_context
        )
        reply = ask_gemini(request.user, enriched_message, history)
    except Exception as exc:
        return JsonResponse({"reply": f"Asistan şu anda yanıt veremiyor: {exc}"}, status=503)

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    history = history[-12:]
    request.session[SESSION_KEY] = history
    request.session.modified = True

    return JsonResponse({"reply": reply})


@login_required
@require_POST
def assistant_clear(request):
    request.session.pop(SESSION_KEY, None)
    request.session.modified = True
    return JsonResponse({"ok": True})
