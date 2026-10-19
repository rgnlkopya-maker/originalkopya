"""Verify Paraşüt company access using only a read-only request."""
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def verify_company_access(company_id, access_token):
    from .parasut_credentials import ParasutCredentialError
    if not str(company_id).isdecimal() or not access_token:
        raise ParasutCredentialError("Firma veya erişim bilgisi geçersiz.")
    request = Request(
        "https://api.parasut.com/v4/" + str(company_id) + "/sales_invoices?page%5Bsize%5D=1",
        headers={"Authorization": "Bearer " + access_token, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=12) as response:
            result = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError):
        raise ParasutCredentialError("Paraşüt firma erişimi doğrulanamadı.") from None
    if not isinstance(result, dict) or not isinstance(result.get("data"), list):
        raise ParasutCredentialError("Paraşüt beklenmeyen erişim yanıtı döndürdü.")
    return True
