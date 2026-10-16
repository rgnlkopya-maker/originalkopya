"""BizimHesap transfer primitives. No network call is made by this module."""
import hashlib
import json


class TransferResponseError(ValueError):
    pass


def payload_digest(payload):
    """Stable fingerprint for detecting invoice changes between preview and send."""
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_addinvoice_response(response):
    """Accept only an unambiguous successful AddInvoice response.

    A timeout or undecodable response must be marked UNKNOWN, never retried
    automatically, because BizimHesap may have already created the invoice.
    """
    if not isinstance(response, dict):
        raise TransferResponseError("BizimHesap yanıtı geçerli bir nesne değil.")
    error = response.get("error")
    if error is not None and not isinstance(error, str):
        raise TransferResponseError("BizimHesap hata alanı beklenenden farklı.")
    if error:
        raise TransferResponseError("BizimHesap fatura kaydını reddetti.")
    guid = response.get("guid")
    if not isinstance(guid, str) or not guid.strip() or len(guid) > 100:
        raise TransferResponseError("Fatura kimliği doğrulanamadı; tekrar gönderim güvenli değil.")
    return {"guid": guid.strip()}
