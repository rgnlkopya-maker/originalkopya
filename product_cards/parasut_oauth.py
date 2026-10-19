"""Paraşüt OAuth helpers. No passwords, tokens or client secrets in source code.

The registered redirect URI is urn:ietf:wg:oauth:2.0:oob.
Only an operator-initiated authorization-code exchange is supported.
"""
import json
import os
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
    request = Request(TOKEN_URL, data=urlencode(fields).encode("utf-8"), method="POST",
                      headers={"Content-Type": "application/x-www-form-urlencoded",
                               "Accept": "application/json"})
    try:
        with urlopen(request, timeout=15) as response:
            tokens = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError):
        raise ParasutOAuthError("Paraşüt OAuth işlemi başarısız. Yetkileri kontrol edin.") from None
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
