from django.db import models
from django.conf import settings
from core.models import Order


class InvoiceDraft(models.Model):
    STATUS = [("DRAFT", "Taslak"), ("FINAL", "Faturalandırıldı"), ("OPEN", "Açık Hesap")]
    customer = models.ForeignKey("core.Musteri", on_delete=models.PROTECT, related_name="invoice_drafts")
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=8, choices=STATUS, default="DRAFT")
    currency = models.CharField(max_length=3, default="TRY")
    official_number = models.CharField(max_length=80, blank=True, default="")
    show_open_account_in_list = models.BooleanField(default=False)
    bizimhesap_manual_recorded = models.BooleanField(default=False)
    parasut_manual_recorded = models.BooleanField(default=False)
    bizimhesap_display_status = models.CharField(max_length=8, blank=True, default="", choices=[("", "Otomatik"), ("no", "İşlenmedi"), ("yes", "Elle İşlendi"), ("api", "API ile Aktarıldı"), ("skip", "Aktarılmayacak")])
    parasut_display_status = models.CharField(max_length=8, blank=True, default="", choices=[("", "Otomatik"), ("no", "İşlenmedi"), ("yes", "Elle İşlendi"), ("api", "API ile Aktarıldı"), ("skip", "Aktarılmayacak")])
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


class ParasutInvoiceTransfer(models.Model):
    """One Paraşüt sales-invoice record per MoliApp invoice (not an e-document)."""
    invoice = models.OneToOneField(InvoiceDraft, on_delete=models.PROTECT, related_name="parasut_transfer")
    status = models.CharField(max_length=16, default="NOT_SENT", choices=[
        ("NOT_SENT", "Gönderilmedi"), ("SENDING", "Gönderiliyor"),
        ("SENT", "Paraşüt'e kaydedildi"), ("UNKNOWN", "Kontrol gerekli"),
    ])
    external_invoice_id = models.CharField(max_length=100, blank=True, default="")
    external_invoice_no = models.CharField(max_length=100, blank=True, default="")
    official_number_synced_at = models.DateTimeField(null=True, blank=True)
    payload_fingerprint = models.CharField(max_length=64, blank=True, default="")
    needs_sync = models.BooleanField(default=False)
    deleted_external_invoice_id = models.CharField(max_length=100, blank=True, default="")
    deleted_verified_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=255, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)


class ParasutCustomerMapping(models.Model):
    customer = models.OneToOneField("core.Musteri", on_delete=models.CASCADE, related_name="parasut_mapping")
    external_contact_id = models.CharField(max_length=100, unique=True)
    updated_at = models.DateTimeField(auto_now=True)


class ParasutProductMapping(models.Model):
    product_code = models.CharField(max_length=150, unique=True)
    external_product_id = models.CharField(max_length=100, unique=True)
    updated_at = models.DateTimeField(auto_now=True)


class ParasutOAuthCredential(models.Model):
    """Encrypted OAuth token pair; single connected Paraşüt company."""
    company_id = models.CharField(max_length=30, unique=True)
    access_token_encrypted = models.TextField()
    refresh_token_encrypted = models.TextField()
    expires_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)


class InvoiceStatusHistory(models.Model):
    invoice = models.ForeignKey(InvoiceDraft, on_delete=models.PROTECT, related_name='status_history')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    previous_status = models.CharField(max_length=8)
    new_status = models.CharField(max_length=8)
    previous_official_number = models.CharField(max_length=80, blank=True, default='')
    changed_at = models.DateTimeField(auto_now_add=True)



class StandaloneInvoice(models.Model):
    """A manually entered invoice or a non-exportable proforma."""
    is_proforma = models.BooleanField(default=False)
    customer = models.ForeignKey("core.Musteri", on_delete=models.PROTECT)
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="TRY")
    note = models.TextField(blank=True, default="")
    official_number = models.CharField(max_length=80, blank=True, default="")
    show_open_account_in_list = models.BooleanField(default=False)
    bizimhesap_display_status = models.CharField(max_length=8, blank=True, default="")
    parasut_display_status = models.CharField(max_length=8, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class StandaloneInvoiceLine(models.Model):
    order = models.OneToOneField("core.Order", null=True, blank=True, on_delete=models.PROTECT, related_name="standalone_invoice_line")
    invoice = models.ForeignKey(StandaloneInvoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit = models.CharField(max_length=20, default="Adet")
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    vat_rate = models.DecimalField(max_digits=7, decimal_places=2, default=10)


class StandaloneInvoiceTransfer(models.Model):
    """Manual invoice platform delivery lock; uncertain results block retries."""
    invoice = models.ForeignKey(StandaloneInvoice, on_delete=models.PROTECT, related_name="transfers")
    platform = models.CharField(max_length=16, choices=[("bizimhesap", "BizimHesap"), ("parasut", "Paraşüt")])
    status = models.CharField(max_length=16, default="NOT_SENT")
    external_invoice_id = models.CharField(max_length=100, blank=True, default="")
    last_error = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["invoice", "platform"], name="unique_standalone_invoice_platform")]


class CompanyInvoiceProfile(models.Model):
    """Local display-only sender details. Not included in accounting API payloads."""
    company_name = models.CharField(max_length=250, blank=True, default="")
    address = models.TextField(blank=True, default="")
    tax_office = models.CharField(max_length=120, blank=True, default="")
    tax_number = models.CharField(max_length=30, blank=True, default="")
    mersis_number = models.CharField(max_length=40, blank=True, default="")
    registry_number = models.CharField(max_length=50, blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    iban = models.CharField(max_length=60, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)


class InvoiceFreeDelivery(models.Model):
    order = models.OneToOneField("core.Order", on_delete=models.PROTECT, related_name="invoice_free_delivery")
    explanation = models.TextField()
    created_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class LegacyInvoiceAcknowledgement(models.Model):
    order = models.OneToOneField("core.Order", on_delete=models.PROTECT, related_name="legacy_invoice_acknowledgement")
    note = models.TextField(default="Geçmiş dönemde faturaya bağlandığı bildirildi; MoliApp içinde FT bağlantısı bulunmuyor.")
    recorded_at = models.DateTimeField(auto_now_add=True)


class SharedInvoiceNumber(models.Model):
    """A single unique FT number across order-based and manually created invoices."""
    number = models.PositiveIntegerField(unique=True)
    draft = models.OneToOneField("InvoiceDraft", null=True, blank=True, on_delete=models.CASCADE, related_name="shared_number")
    manual = models.OneToOneField("StandaloneInvoice", null=True, blank=True, on_delete=models.CASCADE, related_name="shared_number")


class InvoiceNumberSequence(models.Model):
    """Singleton, transactionally locked to allocate invoice numbers."""
    last_number = models.PositiveIntegerField(default=0)
