"""Encrypted persistence for Paraşüt OAuth credentials. Never logs token values."""
import os
from datetime import timedelta
from cryptography.fernet import Fernet, InvalidToken
from django.db import transaction
from django.utils import timezone
from .invoice_models import ParasutOAuthCredential


class ParasutCredentialError(Exception):
    pass


def _cipher():
    key = os.environ.get("PARASUT_TOKEN_ENCRYPTION_KEY", "").strip()
    if not key:
        raise ParasutCredentialError("Paraşüt token şifreleme anahtarı tanımlı değil.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError):
        raise ParasutCredentialError("Paraşüt token şifreleme anahtarı geçersiz.") from None


def save_tokens(company_id, oauth_response):
    if not str(company_id).isdecimal():
        raise ParasutCredentialError("Geçersiz firma ID.")
    access = oauth_response.get("access_token")
    refresh = oauth_response.get("refresh_token")
    if not access or not refresh:
        raise ParasutCredentialError("Paraşüt eksik token çifti döndürdü.")
    try:
        lifetime = max(1, min(int(oauth_response.get("expires_in", 7200)), 86400))
    except (ValueError, TypeError):
        raise ParasutCredentialError("Geçersiz token süresi.") from None
    cipher = _cipher()
    with transaction.atomic():
        ParasutOAuthCredential.objects.update_or_create(
            company_id=str(company_id),
            defaults={
                "access_token_encrypted": cipher.encrypt(access.encode()).decode(),
                "refresh_token_encrypted": cipher.encrypt(refresh.encode()).decode(),
                "expires_at": timezone.now() + timedelta(seconds=lifetime),
            },
        )


def get_tokens(company_id):
    credential = ParasutOAuthCredential.objects.get(company_id=str(company_id))
    cipher = _cipher()
    try:
        return {
            "access_token": cipher.decrypt(credential.access_token_encrypted.encode()).decode(),
            "refresh_token": cipher.decrypt(credential.refresh_token_encrypted.encode()).decode(),
            "expires_at": credential.expires_at,
        }
    except (InvalidToken, ValueError):
        raise ParasutCredentialError("Paraşüt tokenları çözülemedi; anahtar değişmiş olabilir.") from None
