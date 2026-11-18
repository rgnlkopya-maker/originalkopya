"""Google Photos Picker OAuth entry point; no access to a user's library without consent."""
import os
from urllib.parse import urlencode

import requests
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.views.decorators.http import require_POST

from core.models import GalleryGroup

SCOPE = "https://www.googleapis.com/auth/photospicker.mediaitems.readonly"


@login_required
@require_POST
def photos_picker_start(request, group_id):
    if not request.user.is_active:
        return HttpResponseForbidden("Yetkiniz yok.")
    group = get_object_or_404(GalleryGroup, pk=group_id)
    client_id = os.getenv("GOOGLE_PHOTOS_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_PHOTOS_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        messages.error(request, "Google Photos bağlantısı henüz yapılandırılmadı.")
        return redirect(f"/urun-albumu/?album={group.album_id}&group={group.pk}")
    state = get_random_string(48)
    request.session["gallery_photos_oauth"] = {"state": state, "group_id": group.pk, "user_id": request.user.pk}
    redirect_uri = request.build_absolute_uri(reverse("gallery_photos_picker_callback"))
    params = {
        "client_id": client_id, "redirect_uri": redirect_uri,
        "response_type": "code", "scope": SCOPE, "state": state,
        "access_type": "online", "prompt": "consent",
    }
    return redirect("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))


@login_required
def photos_picker_callback(request):
    pending = request.session.pop("gallery_photos_oauth", None)
    if not pending or pending.get("user_id") != request.user.pk or request.GET.get("state") != pending.get("state"):
        return HttpResponseBadRequest("Google Photos bağlantısı doğrulanamadı.")
    group = get_object_or_404(GalleryGroup, pk=pending["group_id"])
    back = f"/urun-albumu/?album={group.album_id}&group={group.pk}"
    code = request.GET.get("code")
    if not code:
        messages.error(request, "Google Photos izni verilmedi.")
        return redirect(back)
    try:
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": os.environ["GOOGLE_PHOTOS_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_PHOTOS_CLIENT_SECRET"],
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": request.build_absolute_uri(reverse("gallery_photos_picker_callback")),
            },
            timeout=15,
        )
        response.raise_for_status()
        access_token = response.json()["access_token"]
        session_response = requests.post(
            "https://photospicker.googleapis.com/v1/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"pickingConfig": {"maxItemCount": "2000"}},
            timeout=15,
        )
        session_response.raise_for_status()
        picker = session_response.json()
        if not picker.get("pickerUri") or not picker.get("id"):
            raise ValueError("Google Photos seçim oturumu eksik.")
        # Store short-lived token only in the server-side session, never in URLs or page markup.
        request.session["gallery_photos_picker"] = {
            "group_id": group.pk, "user_id": request.user.pk,
            "access_token": access_token, "session_id": picker["id"],
        }
        request.session["gallery_photos_picker"]["picker_uri"] = picker["pickerUri"]
        return redirect(reverse("gallery_photos_picker_wait"))
    except (requests.RequestException, KeyError, ValueError):
        messages.error(request, "Google Photos seçim ekranı açılamadı. Lütfen tekrar deneyin.")
        return redirect(back)


@login_required
def photos_picker_wait(request):
    """Show a local return point while Google Photos selection runs in another tab."""
    pending = request.session.get("gallery_photos_picker") or {}
    if pending.get("user_id") != request.user.pk:
        return HttpResponseBadRequest("Aktif Google Photos seçimi bulunamadı.")
    from django.shortcuts import render
    return render(request, "core/gallery_photos_picker_wait.html", {
        "picker_uri": pending["picker_uri"],
        "group_id": pending["group_id"],
    })


@login_required
def photos_picker_status(request):
    """Poll Google Picker; never expose OAuth credentials to the browser."""
    pending = request.session.get("gallery_photos_picker") or {}
    if pending.get("user_id") != request.user.pk:
        return JsonResponse({"error": "Oturum bulunamadı."}, status=400)
    session_id = pending["session_id"]
    try:
        response = requests.get(
            "https://photospicker.googleapis.com/v1/sessions/" + session_id,
            headers={"Authorization": "Bearer " + pending["access_token"]},
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("mediaItemsSet"):
            return JsonResponse({"ready": False})
        items = []
        page_token = None
        while len(items) < 2000:
            params = {"sessionId": session_id, "pageSize": 100}
            if page_token:
                params["pageToken"] = page_token
            result = requests.get(
                "https://photospicker.googleapis.com/v1/mediaItems",
                headers={"Authorization": "Bearer " + pending["access_token"]},
                params=params, timeout=20,
            )
            result.raise_for_status()
            body = result.json()
            for media in body.get("mediaItems", []):
                items.append({
                    "id": media.get("id"),
                    "filename": media.get("mediaFile", {}).get("filename", ""),
                    "mimeType": media.get("mediaFile", {}).get("mimeType", ""),
                })
            page_token = body.get("nextPageToken")
            if not page_token:
                break
        return JsonResponse({"ready": True, "count": len(items), "items": items[:2000]})
    except requests.RequestException:
        return JsonResponse({"error": "Google Photos durumu alınamadı. Yeniden deneyin."}, status=502)
