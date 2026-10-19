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



def valid_access_token(company_id):
    """Return stored access token, refreshing the encrypted pair under a DB row lock."""
    from datetime import timedelta
    from django.utils import timezone
    from .parasut_oauth import refresh_tokens
    cipher = _cipher()
    with transaction.atomic():
        try:
            row = ParasutOAuthCredential.objects.select_for_update().get(company_id=str(company_id))
        except ParasutOAuthCredential.DoesNotExist:
            raise ParasutCredentialError("Paraşüt hesabı henüz yetkilendirilmedi.") from None
        try:
            access = cipher.decrypt(row.access_token_encrypted.encode()).decode()
        except (InvalidToken, ValueError):
            raise ParasutCredentialError("Paraşüt erişim tokenı çözülemedi.") from None
        if row.expires_at > timezone.now() + timedelta(minutes=5):
            return access
        try:
            old_refresh = cipher.decrypt(row.refresh_token_encrypted.encode()).decode()
        except (InvalidToken, ValueError):
            raise ParasutCredentialError("Paraşüt yenileme tokenı çözülemedi.") from None
        result = refresh_tokens(old_refresh)
        new_access = result["access_token"]
        new_refresh = result["refresh_token"]
        try:
            lifetime = max(1, min(int(result.get("expires_in", 7200)), 86400))
        except (ValueError, TypeError):
            raise ParasutCredentialError("Paraşüt token süresi geçersiz.") from None
        row.access_token_encrypted = cipher.encrypt(new_access.encode()).decode()
        row.refresh_token_encrypted = cipher.encrypt(new_refresh.encode()).decode()
        row.expires_at = timezone.now() + timedelta(seconds=lifetime)
        row.save(update_fields=["access_token_encrypted", "refresh_token_encrypted", "expires_at", "updated_at"])
        return new_access
