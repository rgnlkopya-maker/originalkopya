"""OAuth connection for manual cheque backups. Never display or log tokens."""
import base64
import hashlib
import os
import secrets
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .instrument_models import InstrumentDriveAuthorization

SCOPES = ["https://www.googleapis.com/auth/drive"]
AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


def _allowed(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=("patron", "mudur")).exists())


def _config():
    client_id = os.environ.get("GOOGLE_DRIVE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_DRIVE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Google OAuth Client ID veya Secret Render ortaminda eksik.")
    return client_id, client_secret


def _cipher():
    material = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(material))


def _callback_url(request):
    return request.build_absolute_uri(reverse("instrument_drive_callback"))


def connected():
    return InstrumentDriveAuthorization.objects.filter(key=1).exists()


def drive_service():
    client_id, client_secret = _config()
    row = InstrumentDriveAuthorization.objects.filter(key=1).first()
    if not row:
        raise RuntimeError("Google Drive hesabi henuz baglanmadi.")
    token = _cipher().decrypt(row.encrypted_refresh_token.encode()).decode()
    creds = Credentials(
        token=None, refresh_token=token, token_uri=TOKEN_ENDPOINT,
        client_id=client_id, client_secret=client_secret, scopes=SCOPES,
    )
    creds.refresh(GoogleAuthRequest())
    return build("drive", "v3", credentials=creds, cache_discovery=False)


@login_required
def connect(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Muhasebe yetkiniz yok.")
    try:
        client_id, _ = _config()
        state = secrets.token_urlsafe(32)
        request.session["instrument_drive_oauth_state"] = state
        request.session["instrument_drive_oauth_user"] = request.user.pk
        request.session.modified = True
        params = {
            "client_id": client_id,
            "redirect_uri": _callback_url(request),
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return redirect(AUTH_ENDPOINT + "?" + urlencode(params))
    except Exception:
        messages.error(request, "Google baglanti ayarlari eksik. Render OAuth ayarlarini kontrol edin.")
        return redirect("instrument_list")


@login_required
def callback(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Muhasebe yetkiniz yok.")
    state = request.session.pop("instrument_drive_oauth_state", None)
    user_id = request.session.pop("instrument_drive_oauth_user", None)
    if not state or not secrets.compare_digest(str(state), str(request.GET.get("state", ""))) or user_id != request.user.pk:
        messages.error(request, "Google baglantisi dogrulanamadi. Tekrar deneyin.")
        return redirect("instrument_list")
    if request.GET.get("error") or not request.GET.get("code"):
        messages.error(request, "Google Drive erisim izni verilmedi.")
        return redirect("instrument_list")
    try:
        client_id, client_secret = _config()
        response = requests.post(
            TOKEN_ENDPOINT,
            data={
                "code": request.GET["code"],
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": _callback_url(request),
                "grant_type": "authorization_code",
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        refresh_token = payload.get("refresh_token")
        if not refresh_token:
            raise RuntimeError("Google kalici erisim anahtari vermedi.")
        encrypted = _cipher().encrypt(refresh_token.encode()).decode()
        InstrumentDriveAuthorization.objects.update_or_create(
            key=1, defaults={"encrypted_refresh_token": encrypted}
        )
        messages.success(request, "Google Drive hesabi baglandi. Simdi Yedekle butonunu kullanabilirsiniz.")
    except Exception:
        messages.error(request, "Google baglantisi tamamlanamadi. OAuth ayarlarini ve yonlendirme adresini kontrol edin.")
    return redirect("instrument_list")


@login_required
@require_POST
def disconnect(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Muhasebe yetkiniz yok.")
    InstrumentDriveAuthorization.objects.filter(key=1).delete()
    messages.success(request, "Google Drive baglantisi kaldirildi.")
    return redirect("instrument_list")
