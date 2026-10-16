"""Read-only BizimHesap API client. Never posts invoices or collections."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class BizimHesapError(Exception):
    pass


def list_customers():
    token = os.environ.get("BIZIMHESAP_API_TOKEN", "").strip()
    if not token:
        raise BizimHesapError("BizimHesap API anahtarı Render ortam değişkenine henüz tanımlanmadı.")
    request = Request(
        "https://uygulama.bizimhesap.com/api/b2b/customers",
        headers={"token": token, "Accept": "application/json", "User-Agent": "MoliApp/1.0 (BizimHesap API Integration)"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=12) as response:
            data = json.load(response)
    except HTTPError as exc:
        # Safe, allowlisted diagnostics only; never return the token or raw body.
        content_type = (exc.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        ray = (exc.headers.get("CF-Ray") or "").strip()
        if not (3 <= len(ray) <= 80 and all(c.isalnum() or c in "-_" for c in ray)):
            ray = ""
        server = (exc.headers.get("Server") or "").strip().lower()
        provider = "Cloudflare" if server == "cloudflare" or ray else "belirsiz"
        code = ""
        if content_type == "application/json":
            try:
                payload = json.loads(exc.read(4096).decode("utf-8"))
                if isinstance(payload, dict):
                    for key in ("errorCode", "error_code", "code", "statusCode"):
                        value = payload.get(key)
                        if isinstance(value, (int, str)) and str(value).replace("_", "").replace("-", "").isalnum() and len(str(value)) <= 40:
                            code = str(value)
                            break
            except (ValueError, UnicodeDecodeError):
                pass
        info = [
            f"BizimHesap HTTP {exc.code}",
            f"yanıt türü: {content_type or 'bilinmiyor'}",
            f"koruma sağlayıcısı: {provider}",
        ]
        if code:
            info.append(f"hata kodu: {code}")
        if ray:
            info.append(f"CF-Ray: {ray}")
        raise BizimHesapError(" | ".join(info)) from exc
    except (URLError, TimeoutError) as exc:
        raise BizimHesapError("BizimHesap servisine bağlantı kurulamadı veya zaman aşımına uğradı.") from exc
    except ValueError as exc:
        raise BizimHesapError("BizimHesap JSON yerine beklenmeyen içerik döndürdü.") from exc
    if isinstance(data, dict):
        if data.get("error"):
            raise BizimHesapError("BizimHesap müşteri listesi hata döndürdü.")
        for key in ("customers", "Customers", "data", "Data", "result", "Result"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise BizimHesapError("BizimHesap müşteri yanıt formatı beklenenden farklı.")
    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        code = next((item[k] for k in ("customerId", "CustomerId", "CustomerID", "customerID", "id", "Id", "code", "Code") if item.get(k) is not None), None)
        title = next((item[k] for k in ("title", "Title", "name", "Name", "customerName", "CustomerName") if item.get(k)), None)
        if code is not None and title:
            result.append({"id": str(code), "title": str(title)})
    if data and not result:
        raise BizimHesapError("Cari yanıtındaki kod veya ünvan alanları eşleştirilemedi.")
    return result
