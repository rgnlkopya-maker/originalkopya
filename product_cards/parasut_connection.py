"""Read-only Paraşüt connectivity probe. No invoices or e-documents are created."""
import os
import json
from urllib.request import Request, urlopen


class ParasutConnectionError(Exception):
    pass


def check_connection():
    company = os.getenv("PARASUT_COMPANY_ID", "").strip()
    token = os.getenv("PARASUT_ACCESS_TOKEN", "").strip()
    if not company.isdecimal() or not token:
        raise ParasutConnectionError("Paraşüt firma ID veya erişim tokenı tanımlanmamış.")
    request = Request(
        "https://api.parasut.com/v4/" + company + "/sales_invoices?page%5Bsize%5D=1",
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=12) as response:
            result = json.load(response)
    except Exception:
        raise ParasutConnectionError("Paraşüt okuma bağlantısı doğrulanamadı.") from None
    if not isinstance(result, dict) or "data" not in result:
        raise ParasutConnectionError("Paraşüt beklenmeyen yanıt döndürdü.")
    return True
