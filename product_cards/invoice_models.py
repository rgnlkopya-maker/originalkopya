from django.db import models
from django.conf import settings
from core.models import Order


class InvoiceDraft(models.Model):
    STATUS = [("DRAFT", "Taslak"), ("FINAL", "Faturalandırıldı")]
    customer = models.ForeignKey("core.Musteri", on_delete=models.PROTECT, related_name="invoice_drafts")
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=8, choices=STATUS, default="DRAFT")
    currency = models.CharField(max_length=3, default="TRY")
    official_number = models.CharField(max_length=80, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-invoice_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["customer", "invoice_date", "currency"], condition=models.Q(status="DRAFT"), name="one_open_invoice_per_customer_day_currency")
        ]


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(InvoiceDraft, on_delete=models.CASCADE, related_name="lines")
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="invoice_line")
    price = models.DecimalField(max_digits=14, decimal_places=2)
    vat_rate = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class BizimHesapCustomerMapping(models.Model):
    customer = models.OneToOneField("core.Musteri", on_delete=models.CASCADE, related_name="bizimhesap_mapping")
    external_customer_id = models.CharField(max_length=100)
    invoice_address = models.CharField(max_length=255, blank=True, default="")
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["external_customer_id"], name="unique_bizimhesap_customer_id")]


class BizimHesapInvoiceTransfer(models.Model):
    """One external transfer record per local invoice; no automatic API writes."""
    invoice = models.OneToOneField(InvoiceDraft, on_delete=models.PROTECT, related_name="bizimhesap_transfer")
    status = models.CharField(max_length=16, default="NOT_SENT", choices=[
        ("NOT_SENT", "Gönderilmedi"), ("SENDING", "Gönderiliyor"),
        ("SENT", "Aktarıldı"), ("UNKNOWN", "Kontrol gerekli"),
    ])
    external_invoice_id = models.CharField(max_length=100, blank=True, default="")
    external_invoice_no = models.CharField(max_length=100, blank=True, default="")
    payload_fingerprint = models.CharField(max_length=64, blank=True, default="")
    last_error = models.CharField(max_length=255, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)
