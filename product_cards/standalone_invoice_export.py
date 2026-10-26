"""Manual invoices reuse existing accounting payload builders and API primitives.

No automatic e-document issuance. Fail closed on unknown delivery outcomes.
"""
import json
import os
from urllib.request import Request, urlopen
from django.db import transaction
from .invoice_models import (
    StandaloneInvoice, StandaloneInvoiceTransfer,
    BizimHesapCustomerMapping, ParasutCustomerMapping,
)
from .bizimhesap_payload import build_invoice_payload
from .bizimhesap_transfer import parse_addinvoice_response, TransferResponseError
from .parasut_payload import build_parasut_sales_invoice, validate_parasut_vat_payload
from .parasut_export_service import _request, _product, ParasutExportError
from .parasut_credentials import valid_access_token


class ManualTransferError(Exception):
    pass


def send_manual_invoice(invoice_id, platform):
    if platform not in ("bizimhesap", "parasut"):
        raise ManualTransferError("Muhasebe platformu geçersiz.")
    enable_var = "BIZIMHESAP_INVOICE_EXPORT_ENABLED" if platform == "bizimhesap" else "PARASUT_INVOICE_EXPORT_ENABLED"
    if os.environ.get(enable_var) != "true":
        raise ManualTransferError("Bu muhasebe entegrasyonu kapalı.")
    with transaction.atomic():
        invoice = StandaloneInvoice.objects.select_for_update().select_related("customer").get(pk=invoice_id)
        if invoice.is_proforma:
            raise ManualTransferError("Proforma faturalar muhasebe sistemlerine aktarılamaz.")
        rows = list(invoice.lines.order_by("id"))
        if not rows:
            raise ManualTransferError("Boş fatura gönderilemez.")
        rec, _ = StandaloneInvoiceTransfer.objects.select_for_update().get_or_create(invoice=invoice, platform=platform)
        if rec.status != "NOT_SENT":
            raise ManualTransferError("Önceki aktarım var veya sonucu belirsiz. Mükerrer gönderim engellendi.")
        if platform == "bizimhesap":
            mapping = BizimHesapCustomerMapping.objects.filter(customer=invoice.customer).first()
            firm_id = (os.environ.get("BIZIMHESAP_FIRM_ID") or os.environ.get("BIZIMHESAP_API_TOKEN") or "").strip()
            payload, errors = build_invoice_payload(invoice, rows, mapping, firm_id)
        else:
            if not ParasutCustomerMapping.objects.filter(customer=invoice.customer).exists():
                raise ManualTransferError("Paraşüt carisini eşleştirin.")
            company = os.environ.get("PARASUT_COMPANY_ID", "").strip()
            if not company.isdecimal():
                raise ManualTransferError("Paraşüt firma kimliği tanımsız.")
            temporary_codes = {str(row.description).strip(): "CHECK" for row in rows}
            payload, errors = build_parasut_sales_invoice(invoice, temporary_codes, lines_override=rows)
            if not errors and not validate_parasut_vat_payload(payload, len(rows)):
                errors = ["Paraşüt aktarımında bütün satırlar %10 KDV olmalıdır."]
        if errors or payload is None:
            raise ManualTransferError("; ".join(errors) or "Fatura doğrulanamadı.")
        rec.status = "SENDING"
        rec.last_error = ""
        rec.save(update_fields=["status", "last_error", "updated_at"])
    try:
        if platform == "bizimhesap":
            request = Request(
                "https://uygulama.bizimhesap.com/api/b2b/addinvoice",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "MoliApp/1.0"},
                method="POST",
            )
            with urlopen(request, timeout=20) as response:
                remote = json.load(response)
            external_id = parse_addinvoice_response(remote)["guid"]
        else:
            token = valid_access_token(company)
            product_ids = {}
            for row in rows:
                code = str(row.description).strip()
                if code not in product_ids:
                    product_ids[code] = _product(company, token, code, row.vat_rate)
            payload, errors = build_parasut_sales_invoice(invoice, product_ids, lines_override=rows)
            if errors or not validate_parasut_vat_payload(payload, len(rows)):
                raise ManualTransferError("; ".join(errors) or "KDV doğrulaması başarısız.")
            remote = _request(company, token, "sales_invoices", "POST", payload)
            external_id = str((remote.get("data") or {}).get("id") or "")
            if not external_id:
                raise ManualTransferError("Paraşüt yanıtı doğrulanamadı.")
    except Exception as exc:
        with transaction.atomic():
            rec = StandaloneInvoiceTransfer.objects.select_for_update().get(invoice_id=invoice_id, platform=platform)
            rec.status = "UNKNOWN"
            rec.last_error = "Dış kaydın oluşup oluşmadığı kontrol edilmeli."
            rec.save(update_fields=["status", "last_error", "updated_at"])
        raise ManualTransferError("Aktarım sonucu doğrulanamadı. Muhasebe sistemi kontrol edilmeden yeniden göndermeyin.") from None
    with transaction.atomic():
        rec = StandaloneInvoiceTransfer.objects.select_for_update().get(invoice_id=invoice_id, platform=platform)
        rec.status = "SENT"
        rec.external_invoice_id = external_id
        rec.last_error = ""
        rec.save(update_fields=["status", "external_invoice_id", "last_error", "updated_at"])
    return external_id
