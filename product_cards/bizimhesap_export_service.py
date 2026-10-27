"""BizimHesap transfer state machine. Intentionally no outbound HTTP implementation."""
import os
import json
from urllib.request import Request, urlopen
from django.db import transaction
from .invoice_models import InvoiceDraft, BizimHesapCustomerMapping, BizimHesapInvoiceTransfer
from .bizimhesap_payload import build_invoice_payload
from .bizimhesap_transfer import payload_digest, parse_addinvoice_response, TransferResponseError


class TransferBlocked(Exception):
    pass


def prepare_transfer(invoice_id):
    """Check and freeze a unique transfer intent. Never sends anything remotely."""
    if os.environ.get("BIZIMHESAP_INVOICE_EXPORT_ENABLED") != "true":
        raise TransferBlocked("Gerçek BizimHesap aktarımı henüz etkinleştirilmedi.")
    with transaction.atomic():
        invoice = InvoiceDraft.objects.select_for_update().select_related("customer").get(pk=invoice_id)
        previous = BizimHesapInvoiceTransfer.objects.select_for_update().filter(invoice=invoice).first()
        if previous and previous.status in ("SENDING", "SENT", "UNKNOWN"):
            raise TransferBlocked("Bu fatura gönderilmiş veya sonucu henüz doğrulanmamış.")
        if invoice.bizimhesap_manual_recorded:
            raise TransferBlocked("Fatura BizimHesap için elle işlendi olarak işaretlenmiş. Mükerrer gönderim engellendi.")
        mapping = BizimHesapCustomerMapping.objects.filter(customer=invoice.customer).first()
        lines = list(invoice.lines.select_related("order").order_by("id")) + list(invoice.manual_lines.order_by("id"))
        firm_id = (os.environ.get("BIZIMHESAP_FIRM_ID") or os.environ.get("BIZIMHESAP_API_TOKEN") or "").strip()
        payload, problems = build_invoice_payload(invoice, lines, mapping, firm_id)
        if problems or payload is None:
            raise TransferBlocked("; ".join(problems) or "Fatura verisi hazırlanamadı.")
        fingerprint = payload_digest(payload)
        record, _ = BizimHesapInvoiceTransfer.objects.update_or_create(
            invoice=invoice, defaults={
                "status": "SENDING", "payload_fingerprint": fingerprint,
                "external_invoice_id": "", "external_invoice_no": "", "last_error": "",
            })
        return record.pk, payload


def record_response(transfer_id, response=None, failure=None):
    """Conservatively record result. Ambiguous outcomes require manual reconciliation."""
    with transaction.atomic():
        transfer = BizimHesapInvoiceTransfer.objects.select_for_update().get(pk=transfer_id)
        if transfer.status != "SENDING":
            raise TransferBlocked("Aktarım durumu değişti, sonuç tekrar işlenemez.")
        if failure is not None:
            transfer.status = "UNKNOWN"
            transfer.last_error = "İşlemin dış sistemde tamamlanıp tamamlanmadığı kontrol edilmeli."
        else:
            try:
                result = parse_addinvoice_response(response)
            except TransferResponseError:
                transfer.status = "UNKNOWN"
                if isinstance(response, dict) and isinstance(response.get("error"), str) and response["error"].strip():
                    # Log only a bounded, printable error message; never the response payload or API key.
                    reason = "".join(ch for ch in response["error"] if ch.isprintable())[:180]
                    transfer.last_error = "BizimHesap reddetti: " + reason
                else:
                    transfer.last_error = "API sonucu belirsiz; yeniden gönderim yapılmaz."
            else:
                transfer.status = "SENT"
                transfer.external_invoice_id = result["guid"]
                transfer.last_error = ""
        transfer.save(update_fields=["status", "external_invoice_id", "last_error", "updated_at"])
        return transfer.status


def deliver_prepared_invoice(transfer_id, payload):
    """Execute one guarded delivery; never retry automatically."""
    if os.environ.get("BIZIMHESAP_INVOICE_EXPORT_ENABLED") != "true":
        raise TransferBlocked("BizimHesap fatura aktarımı kapalı.")
    with transaction.atomic():
        transfer = BizimHesapInvoiceTransfer.objects.select_for_update().get(pk=transfer_id)
        if transfer.status != "SENDING" or transfer.payload_fingerprint != payload_digest(payload):
            raise TransferBlocked("Aktarım durumu veya fatura içeriği değişti.")
    request = Request(
        "https://uygulama.bizimhesap.com/api/b2b/addinvoice",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "MoliApp/1.0"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            result = json.load(response)
    except Exception:
        return record_response(transfer_id, failure=True)
    return record_response(transfer_id, response=result)
