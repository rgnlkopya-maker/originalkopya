from django.conf import settings
from django.db import models


class NegotiableInstrument(models.Model):
    KIND = [("CHECK", "Çek"), ("NOTE", "Senet"), ("CK_CUST", "Müşteri Çeki"), ("CK_END", "Cirolu Müşteri Çeki"), ("CK_OWN", "Kendi Çekimiz"), ("NT_CUST", "Müşteri Senedi"), ("NT_END", "Cirolu Müşteri Senedi"), ("NT_OWN", "Kendi Senedimiz")]
    KIND_OPTIONS = KIND[2:]
    DIRECTION = [("IN", "Alınan"), ("OUT", "Verilen")]
    STATUS = [("PORTFOLIO", "Portföyde"), ("ISSUED", "Ödeme bekliyor"), ("ENDORSED", "Ciro edildi"), ("BANK", "Bankada"), ("COLLECTED", "Tahsil edildi"), ("PAID", "Ödendi"), ("RETURNED", "İade"), ("BOUNCED", "Karşılıksız"), ("CANCELLED", "İptal")]
    kind = models.CharField(max_length=8, choices=KIND)
    direction = models.CharField(max_length=3, choices=DIRECTION)
    customer = models.ForeignKey("core.Musteri", on_delete=models.PROTECT, related_name="instruments", null=True, blank=True, help_text="Cari hesabına işlenecek MoliApp müşterisi")
    issuer_name = models.CharField(max_length=250, help_text="Çek sahibi/keşideci veya senet borçlusu")
    received_from = models.CharField(max_length=250, blank=True, default="")
    given_to = models.CharField(max_length=250, blank=True, default="")
    bank = models.CharField(max_length=200, blank=True, default="")
    branch = models.CharField(max_length=120, blank=True, default="")
    document_number = models.CharField(max_length=120, blank=True, default="")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, choices=[("TRY","TL"),("USD","USD"),("EUR","EUR"),("GBP","GBP")], default="TRY")
    issue_date = models.DateField(null=True, blank=True)
    transaction_date = models.DateField(null=True, blank=True)
    given_date = models.DateField(null=True, blank=True)
    due_date = models.DateField()
    status = models.CharField(max_length=16, choices=STATUS, default="PORTFOLIO")
    note = models.TextField(blank=True, default="")
    next_photo_sequence = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "-id"]


class InstrumentEndorser(models.Model):
    instrument = models.ForeignKey(NegotiableInstrument, on_delete=models.CASCADE, related_name="endorsers")
    sequence = models.PositiveIntegerField()
    name = models.CharField(max_length=250)
    note = models.CharField(max_length=300, blank=True, default="")
    class Meta:
        ordering = ["sequence", "id"]
        constraints = [models.UniqueConstraint(fields=["instrument","sequence"], name="unique_instrument_endorser_sequence")]


class InstrumentMovement(models.Model):
    instrument = models.ForeignKey(NegotiableInstrument, on_delete=models.CASCADE, related_name="movements")
    action = models.CharField(max_length=40)
    description = models.TextField(blank=True, default="")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created_at", "-id"]


class InstrumentPhoto(models.Model):
    instrument = models.ForeignKey(NegotiableInstrument, on_delete=models.CASCADE, related_name="photos")
    side = models.CharField(max_length=5, choices=[("FRONT","Ön"),("BACK","Arka")])
    storage_path = models.CharField(max_length=450)
    original_name = models.CharField(max_length=255, blank=True, default="")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["instrument","side"], name="unique_instrument_photo_side")]


class InstrumentAttachment(models.Model):
    instrument = models.ForeignKey(NegotiableInstrument, on_delete=models.CASCADE, related_name="attachments")
    sequence = models.PositiveIntegerField()
    storage_path = models.CharField(max_length=450)
    original_name = models.CharField(max_length=255, blank=True, default="")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [models.UniqueConstraint(fields=["instrument", "sequence"], name="unique_instrument_attachment_sequence")]


class InstrumentDriveAuthorization(models.Model):
    """Single encrypted OAuth refresh credential for manual accounting backups."""
    key = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    encrypted_refresh_token = models.TextField()
    connected_at = models.DateTimeField(auto_now=True)


class InstrumentBackupRun(models.Model):
    """Audit of manual Drive backup attempts without storing personal document data."""
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    success = models.BooleanField(default=False)
    record_count = models.PositiveIntegerField(default=0)
    new_photo_count = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=40, blank=True, default="")

    class Meta:
        ordering = ["-started_at", "-id"]


class InstrumentDriveHealth(models.Model):
    key = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    status = models.CharField(max_length=16, default="unchecked")
    message = models.CharField(max_length=250, blank=True, default="")
    checked_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
