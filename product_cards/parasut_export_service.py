"""Explicit Paraşüt sales record export; NEVER creates or sends an e-document."""
import hashlib
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.db import transaction
from .invoice_models import InvoiceDraft, ParasutInvoiceTransfer, ParasutCustomerMapping

UA = "MoliApp/1.0 (+https://originalkopya.onrender.com)"

class ParasutExportError(Exception):
    pass

def _request(company, token, path, method="GET", payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request("https://api.parasut.com/v4/" + company + "/" + path, data=data, method=method,
                  headers={"Authorization": "Bearer " + token, "Accept": "application/json",
                           "Content-Type": "application/json", "User-Agent": UA})
    try:
        with urlopen(req, timeout=20) as response:
            return json.load(response)
    except HTTPError as exc:
        raise ParasutExportError("Paraşüt HTTP " + str(exc.code) + "; işlem sonucu Paraşüt'ten kontrol edilmeli.") from None
    except (URLError, TimeoutError, ValueError):
        raise ParasutExportError("Paraşüt erişimi veya yanıtı doğrulanamadı; tekrar gönderimden önce dış kayıt kontrol edilmeli.") from None

def _product(company, token, code, rate):
    from .invoice_models import ParasutProductMapping
    existing = ParasutProductMapping.objects.filter(product_code=code).first()
    if existing:
        return existing.external_product_id
    query = urlencode({"filter[code]": code, "page[size]": 25})
    rows = _request(company, token, "products?" + query).get("data", [])
    exact = [p for p in rows if isinstance(p, dict) and str((p.get("attributes") or {}).get("code") or "").strip() == code]
    if len(exact) > 1:
        raise ParasutExportError("Paraşüt ürün kodu birden fazla kayıtla eşleşiyor: " + code)
    if exact:
        pid = str(exact[0]["id"])
    else:
        result = _request(company, token, "products", "POST", {"data": {"type": "products", "attributes": {
            "code": code, "name": code, "vat_rate": float(rate), "unit": "Adet",
            "inventory_tracking": False
        }}})
        pid = str((result.get("data") or {}).get("id") or "")
        if not pid:
            raise ParasutExportError("Ürün oluşturma yanıtında ID yok; Paraşüt kontrol edilmeli.")
    # Mapping records are merely a cache of verified remote IDs.
    from django.db import IntegrityError
    try:
        ParasutProductMapping.objects.update_or_create(product_code=code, defaults={"external_product_id": pid})
    except IntegrityError:
        raise ParasutExportError("Ürün eşleştirme çakışması; Paraşüt kaydını kontrol edin.") from None
    return pid

def send_sales_record(invoice_id):
    """Single explicit operator action. Fail-closed on any uncertain outcome."""
    if os.environ.get("PARASUT_INVOICE_EXPORT_ENABLED") != "true":
        raise ParasutExportError("Paraşüt satış kaydı aktarımı kapalı (PARASUT_INVOICE_EXPORT_ENABLED).")
    allowed = os.environ.get("PARASUT_FIRST_TEST_INVOICE_ID", "").strip()
    if allowed and allowed != str(invoice_id):
        raise ParasutExportError("İlk test yalnızca izin verilen fatura için açık.")
    company = os.environ.get("PARASUT_COMPANY_ID", "").strip()
    if not company.isdecimal():
        raise ParasutExportError("Paraşüt firma ID eksik.")
    with transaction.atomic():
        invoice = InvoiceDraft.objects.select_for_update().select_related("customer").get(pk=invoice_id)
        if invoice.status != "DRAFT" or invoice.parasut_manual_recorded:
            raise ParasutExportError("Fatura aktarılabilir taslak durumunda değil.")
        if not ParasutCustomerMapping.objects.filter(customer=invoice.customer).exists():
            raise ParasutExportError("Önce Paraşüt carisini eşleştirin.")
        previous = ParasutInvoiceTransfer.objects.select_for_update().filter(invoice=invoice).first()
        if previous and previous.status != "NOT_SENT":
            raise ParasutExportError("Önceki aktarım var veya sonucu belirsiz; mükerrer kayıt engellendi.")
        lines = list(invoice.lines.select_related("order").order_by("id"))
        if not lines or any(not str(line.order.urun_kodu or "").strip() for line in lines):
            raise ParasutExportError("Ürün kodu eksik veya fatura boş.")
        from .parasut_payload import build_parasut_sales_invoice
        # Existing mappings alone are sufficient for initial validation; no API writes yet.
        temporary_ids = {str(line.order.urun_kodu).strip(): "CHECK" for line in lines}
        _, blockers = build_parasut_sales_invoice(invoice, temporary_ids)
        if blockers:
            raise ParasutExportError("; ".join(blockers))
        transfer, _ = ParasutInvoiceTransfer.objects.get_or_create(invoice=invoice)
        transfer.status = "SENDING"
        transfer.last_error = ""
        transfer.save(update_fields=["status", "last_error", "updated_at"])
    # External writes occur OUTSIDE the DB transaction; lock status prevents replay.
    try:
        from .parasut_credentials import valid_access_token
        token = valid_access_token(company)
        codes = {}
        for line in lines:
            code = str(line.order.urun_kodu).strip()
            if code not in codes:
                codes[code] = _product(company, token, code, line.vat_rate)
        payload, errors = build_parasut_sales_invoice(invoice, codes)
        if errors or not payload:
            raise ParasutExportError("; ".join(errors) or "Fatura verileri hazırlanamadı.")
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with transaction.atomic():
            record = ParasutInvoiceTransfer.objects.select_for_update().get(invoice_id=invoice_id)
            record.payload_fingerprint = fingerprint
            record.save(update_fields=["payload_fingerprint", "updated_at"])
        response = _request(company, token, "sales_invoices", "POST", payload)
        remote_id = str((response.get("data") or {}).get("id") or "")
        if not remote_id:
            raise ParasutExportError("Paraşüt yanıtında satış kaydı ID'si yok; tekrar göndermeyin.")
    except Exception as exc:
        with transaction.atomic():
            record = ParasutInvoiceTransfer.objects.select_for_update().get(invoice_id=invoice_id)
            record.status = "UNKNOWN"
            record.last_error = "Aktarım sonucu manuel kontrol edilmeli."
            record.save(update_fields=["status", "last_error", "updated_at"])
        if isinstance(exc, ParasutExportError):
            raise
        raise ParasutExportError("Aktarım sırasında belirsiz hata; Paraşüt kontrol edilmeden tekrar denenmemeli.") from None
    with transaction.atomic():
        record = ParasutInvoiceTransfer.objects.select_for_update().get(invoice_id=invoice_id)
        record.status = "SENT"
        record.external_invoice_id = remote_id
        record.last_error = ""
        record.save(update_fields=["status", "external_invoice_id", "last_error", "updated_at"])
    return remote_id


def update_sales_record(invoice_id):
    """Explicit update of the SAME Paraşüt sales invoice, never POST another record."""
    company = os.environ.get("PARASUT_COMPANY_ID", "").strip()
    if not company.isdecimal():
        raise ParasutExportError("Paraşüt firma bilgisi eksik.")
    with transaction.atomic():
        inv = InvoiceDraft.objects.select_for_update().select_related("customer").get(pk=invoice_id)
        rec = ParasutInvoiceTransfer.objects.select_for_update().filter(invoice=inv).first()
        if not rec or rec.status != "SENT" or not rec.external_invoice_id:
            raise ParasutExportError("Güncellenebilir Paraşüt aktarım kaydı bulunamadı.")
        if not rec.needs_sync:
            raise ParasutExportError("Paraşüt ile eşitlenmesi gereken bir değişiklik yok.")
        if inv.status != "DRAFT":
            raise ParasutExportError("Yalnızca taslak MoliApp faturası güncellenebilir.")
        remote_id = rec.external_invoice_id
        rec.status = "SENDING"
        rec.save(update_fields=["status", "updated_at"])
    remote_write_started = False
    try:
        from .parasut_credentials import valid_access_token
        from .parasut_payload import build_parasut_sales_invoice
        token = valid_access_token(company)
        current = _request(company, token, "sales_invoices/" + remote_id + "?include=details,active_e_document,payments")
        resource = current.get("data") or {}
        attrs = resource.get("attributes") or {}
        relations = resource.get("relationships") or {}
        if str(resource.get("id")) != remote_id:
            raise ParasutExportError("Paraşüt kaydı eşleşmedi.")
        if (relations.get("active_e_document") or {}).get("data"):
            raise ParasutExportError("Paraşüt faturası resmileşmiş; güncelleme yapılmadı.")
        if (relations.get("payments") or {}).get("data"):
            raise ParasutExportError("Paraşüt faturasında tahsilat var; güncelleme yapılmadı.")
        if attrs.get("item_type") != "invoice":
            raise ParasutExportError("Paraşüt kayıt tipi uyumsuz.")
        lines = list(inv.lines.select_related("order").order_by("id"))
        product_ids = {}
        for line in lines:
            code = str(line.order.urun_kodu or "").strip()
            if code not in product_ids:
                product_ids[code] = _product(company, token, code, line.vat_rate)
        payload, errors = build_parasut_sales_invoice(inv, product_ids)
        if errors or not payload:
            raise ParasutExportError("; ".join(errors) or "Fatura verisi hazırlanamadı.")
        # Require an exact one-to-one match with existing remote line IDs.
        # This prevents a PUT from inadvertently creating duplicate product details.
        remote_refs = (relations.get("details") or {}).get("data") or []
        remote_items = {str(item.get("id")): item for item in current.get("included", [])
                        if item.get("type") == "sales_invoice_details"}
        desired_items = payload["data"]["relationships"]["details"]["data"]
        if len(remote_refs) != len(desired_items):
            raise ParasutExportError("Paraşüt satır sayısı değişmiş; otomatik güncelleme güvenli değil.")
        available = list(remote_refs)
        for item in desired_items:
            desc = item["attributes"]["description"]
            product = item["relationships"]["product"]["data"]["id"]
            matched = []
            for ref in available:
                saved = remote_items.get(str(ref.get("id")))
                if not saved:
                    continue
                rattrs = saved.get("attributes") or {}
                rproduct = ((saved.get("relationships") or {}).get("product") or {}).get("data") or {}
                if rattrs.get("description") == desc and str(rproduct.get("id")) == str(product):
                    matched.append(ref)
            if len(matched) != 1:
                raise ParasutExportError("Paraşüt ürün satırları güvenle eşleştirilemedi; güncelleme iptal edildi.")
            chosen = matched[0]
            item["id"] = str(chosen["id"])
            available.remove(chosen)
        # Only update the existing remote ID and its verified line IDs.
        payload["data"]["id"] = remote_id
        remote_write_started = True
        result = _request(company, token, "sales_invoices/" + remote_id, "PUT", payload)
        if str((result.get("data") or {}).get("id")) != remote_id:
            raise ParasutExportError("Güncelleme yanıtındaki Paraşüt ID uyuşmuyor; kontrol gerekli.")
    except ParasutExportError as exc:
        ParasutInvoiceTransfer.objects.filter(invoice_id=invoice_id, status="SENDING").update(status="UNKNOWN" if remote_write_started else "SENT", last_error=str(exc)[:255])
        raise
    except Exception:
        ParasutInvoiceTransfer.objects.filter(invoice_id=invoice_id, status="SENDING").update(status="UNKNOWN", last_error="Güncelleme sonucu belirsiz; dış kayıt kontrol edilmeli.")
        raise ParasutExportError("Paraşüt güncelleme sonucu belirsiz; tekrar denemeden önce dış kaydı kontrol edin.") from None
    with transaction.atomic():
        rec = ParasutInvoiceTransfer.objects.select_for_update().get(invoice_id=invoice_id)
        rec.status = "SENT"
        rec.needs_sync = False
        rec.last_error = ""
        rec.save(update_fields=["status", "needs_sync", "last_error", "updated_at"])
    return remote_id
