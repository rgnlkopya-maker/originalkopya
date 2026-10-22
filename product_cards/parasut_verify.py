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
        headers={"Authorization": "Bearer " + access_token, "Accept": "application/json",
                 "User-Agent": "MoliApp/1.0 (+https://originalkopya.onrender.com)"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=12) as response:
            result = json.load(response)
    except HTTPError as exc:
        if exc.code == 401:
            reason = "401: OAuth token kabul edilmedi."
        elif exc.code == 403:
            reason = "403: Bu firma için API erişim yetkisi yok."
        elif exc.code == 404:
            reason = "404: Company ID bulunamadı veya bu hesap için erişilemiyor."
        else:
            reason = f"HTTP {exc.code}: Firma erişimi doğrulanamadı."
        raise ParasutCredentialError(reason) from None
    except (URLError, TimeoutError, ValueError):
        raise ParasutCredentialError("Firma kontrolünde ağ veya yanıt hatası.") from None
    if not isinstance(result, dict) or not isinstance(result.get("data"), list):
        raise ParasutCredentialError("Paraşüt beklenmeyen erişim yanıtı döndürdü.")
    return True
