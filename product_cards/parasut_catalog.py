"""Read-only Paraşüt catalog access for mapping existing records.

Never creates contacts, products, invoices, or e-documents.
"""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ParasutCatalogError(Exception):
    pass


def _fetch(resource, page=1):
    if resource not in ("contacts", "products"):
        raise ParasutCatalogError("İzin verilmeyen kaynak.")
    company = os.environ.get("PARASUT_COMPANY_ID", "").strip()
    if not company.isdecimal():
        raise ParasutCatalogError("Paraşüt firma ID eksik.")
    from .parasut_credentials import valid_access_token, ParasutCredentialError
    try:
        token = valid_access_token(company)
    except ParasutCredentialError:
        raise ParasutCatalogError("Paraşüt OAuth bağlantısı henüz hazır değil.") from None
    if not isinstance(page, int) or not (1 <= page <= 100):
        raise ParasutCatalogError("Geçersiz sayfa numarası.")
    query = urlencode({"page[number]": page, "page[size]": 25})
    request = Request(
        f"https://api.parasut.com/v4/{company}/{resource}?{query}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=12) as response:
            data = json.load(response)
    except HTTPError as exc:
        raise ParasutCatalogError(f"Paraşüt HTTP {exc.code}; erişimi kontrol edin.") from None
    except (URLError, TimeoutError, ValueError):
        raise ParasutCatalogError("Paraşüt okunamadı.") from None
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ParasutCatalogError("Paraşüt yanıt biçimi beklenmiyor.")
    items = []
    for entry in data["data"]:
        if not isinstance(entry, dict):
            continue
        ident = str(entry.get("id") or "").strip()
        attrs = entry.get("attributes") or {}
        if not isinstance(attrs, dict) or not ident:
            continue
        if resource == "contacts":
            label = attrs.get("name")
        else:
            label = attrs.get("name") or attrs.get("code")
        if label:
            items.append({"id": ident, "name": str(label)[:160]})
    return {"items": items, "has_next": bool((data.get("links") or {}).get("next"))}


def list_contacts(page=1):
    return _fetch("contacts", page)


def list_products(page=1):
    return _fetch("products", page)
