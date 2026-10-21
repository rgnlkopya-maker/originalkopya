"""Paraşüt OAuth helpers. No passwords, tokens or client secrets in source code.

The registered redirect URI is urn:ietf:wg:oauth:2.0:oob.
Only an operator-initiated authorization-code exchange is supported.
"""
import json
import os
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

OOB_REDIRECT = "urn:ietf:wg:oauth:2.0:oob"
AUTHORIZE_URL = "https://api.parasut.com/oauth/authorize"
TOKEN_URL = "https://api.parasut.com/oauth/token"


class ParasutOAuthError(Exception):
    pass


def authorization_url():
    client_id = os.getenv("PARASUT_CLIENT_ID", "").strip()
    if not client_id:
        raise ParasutOAuthError("PARASUT_CLIENT_ID eksik.")
    return AUTHORIZE_URL + "?" + urlencode({
        "client_id": client_id,
        "redirect_uri": OOB_REDIRECT,
        "response_type": "code",
    })


def _exchange(form):
    client_id = os.getenv("PARASUT_CLIENT_ID", "").strip()
    client_secret = os.getenv("PARASUT_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise ParasutOAuthError("Paraşüt OAuth kimlik bilgileri eksik.")
    fields = dict(form, client_id=client_id, client_secret=client_secret)
    # Paraşüt support requires application/x-www-form-urlencoded for OAuth.
    request = Request(
        TOKEN_URL,
        data=urlencode(fields).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            tokens = json.load(response)
    except HTTPError as exc:
        # Never log or expose the response body: it may contain credentials.
        # Expose only an allowlisted OAuth error code and transport diagnostics.
        raw = exc.read(4096)
        content_type = (exc.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        category = "unknown"
        safe_detail = ""
        response_shape = "unknown"
        response_kind = "json" if content_type in ("application/json", "application/problem+json") else (
            "html" if content_type == "text/html" else "other"
        )
        if response_kind == "json":
            try:
                data = json.loads(raw.decode("utf-8"))
                if isinstance(data, dict):
                    # Report keys, not their potentially sensitive values.
                    allowed_keys = ("error", "error_description", "message", "errors", "detail", "status", "code")
                    response_shape = ",".join(k for k in allowed_keys if k in data) or "other_keys"
                    detail = data.get("detail")
                    if isinstance(detail, str):
                        cleaned = detail
                        for secret in (client_id, client_secret, form.get("code", ""), form.get("refresh_token", "")):
                            if secret and len(secret) >= 5:
                                cleaned = cleaned.replace(secret, "[GIZLI]")
                        if (len(cleaned) <= 350
                                and not re.search(r"(?i)(bearer\s+\S+|(?:access|refresh)[_-]?token\s*[:=]|client[_-]?secret\s*[:=]|eyJ[A-Za-z0-9_-]{15,}|[A-Za-z0-9_-]{45,})", cleaned)
                                and not any(ch in cleaned for ch in ("<", ">", "\r", "\n"))):
                            safe_detail = cleaned
                        else:
                            safe_detail = "[Hassas veya uzun yanit gizlendi]"
                    value = data.get("error")
                    if value in ("invalid_grant", "invalid_client", "invalid_request",
                                 "unauthorized_client", "unsupported_grant_type", "access_denied"):
                        category = value
                    elif isinstance(data.get("errors"), list):
                        category = "errors_array"
                    elif any(k in data for k in ("message", "detail", "error_description")):
                        category = "message_without_oauth_code"
                elif isinstance(data, list):
                    response_shape = "array"
            except (ValueError, UnicodeDecodeError):
                response_kind = "invalid_json"
        # Header values may carry credentials or user data; report presence only.
        diagnostic_headers = ("cf-ray", "x-request-id", "x-correlation-id", "retry-after")
        present = ",".join(name for name in diagnostic_headers if exc.headers.get(name)) or "none"
        raise ParasutOAuthError(
            f"Token endpoint HTTP {exc.code}; OAuth hata türü: {category}; "
            f"yanıt türü: {response_kind}; JSON alanları: {response_shape}; "
            f"Paraşüt açıklaması: {safe_detail or 'yok'}; tanı başlıkları: {present}."
        ) from None
    except (URLError, TimeoutError, ValueError):
        raise ParasutOAuthError("Paraşüt OAuth servisine erişilemedi veya geçersiz yanıt alındı.") from None
    if not isinstance(tokens, dict) or not tokens.get("access_token") or not tokens.get("refresh_token"):
        raise ParasutOAuthError("Paraşüt geçerli OAuth token çifti döndürmedi.")
    return tokens


def exchange_authorization_code(code):
    if not isinstance(code, str) or not (1 <= len(code.strip()) <= 1024):
        raise ParasutOAuthError("Geçersiz yetkilendirme kodu.")
    return _exchange({"grant_type": "authorization_code",
                      "code": code.strip(), "redirect_uri": OOB_REDIRECT})


def refresh_tokens(refresh_token):
    if not isinstance(refresh_token, str) or not refresh_token.strip():
        raise ParasutOAuthError("Yenileme tokenı eksik.")
    # Caller must persist BOTH returned tokens atomically; old refresh tokens become obsolete.
    return _exchange({"grant_type": "refresh_token", "refresh_token": refresh_token.strip()})
