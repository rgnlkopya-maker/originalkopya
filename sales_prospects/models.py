from django.conf import settings
from django.db import models


COUNTRIES = [
    ("DE", "Almanya"), ("FR", "Fransa"), ("GB", "Birleşik Krallık"),
    ("US", "ABD"), ("NL", "Hollanda"), ("BE", "Belçika"),
    ("AT", "Avusturya"), ("CH", "İsviçre"), ("ES", "İspanya"),
    ("IT", "İtalya"), ("AE", "Birleşik Arap Emirlikleri"),
    ("SA", "Suudi Arabistan"), ("OTHER", "Diğer"),
]


class Prospect(models.Model):
    STATUS = [
        ("NEW", "İncelenecek"), ("REVIEWED", "İncelendi"),
        ("APPROVED", "İletişime uygun"), ("CONTACTED", "Mesaj gönderildi"),
        ("REPLIED", "Yanıt geldi"), ("QUALIFIED", "Potansiyel toptancı"),
        ("CUSTOMER", "Müşteri oldu"), ("REJECTED", "Uygun değil"),
    ]
    SOURCE = [("WEB", "Web araması"), ("MANUAL", "Elle eklendi")]
    name = models.CharField(max_length=180)
    country = models.CharField(max_length=8, choices=COUNTRIES, db_index=True)
    city = models.CharField(max_length=100, blank=True, default="")
    website_url = models.URLField(max_length=500, blank=True)
    instagram_url = models.URLField(max_length=500, blank=True)
    phone_number = models.CharField(max_length=30, blank=True, default="")
    whatsapp_number = models.CharField(max_length=30, blank=True, default="")
    phone_source_url = models.URLField(max_length=500, blank=True, default="")
    whatsapp_source_url = models.URLField(max_length=500, blank=True, default="")
    instagram_source_url = models.URLField(max_length=500, blank=True, default="")
    contact_scan_at = models.DateTimeField(null=True, blank=True)
    contact_scan_note = models.CharField(max_length=250, blank=True, default="")
    source_url = models.URLField(max_length=500, blank=True)
    canonical_url = models.CharField(max_length=500, unique=True)
    source_snippet = models.TextField(blank=True, default="")
    status = models.CharField(max_length=12, choices=STATUS, default="NEW", db_index=True)
    note = models.TextField(blank=True, default="")
    message_draft = models.TextField(blank=True, default="")
    email = models.EmailField(max_length=254, blank=True, default="")
    CONTACT_CLASS = [("UNKNOWN", "Belirsiz"), ("COMPANY", "Tüzel kişi / şirket"), ("PERSON", "Şahıs işletmesi")]
    contact_class = models.CharField(max_length=8, choices=CONTACT_CLASS, default="UNKNOWN")
    EMAIL_BASIS = [
        ("NONE", "İncelenmedi"), ("CONSENT", "Açık iletişim izni"),
        ("US_B2B", "ABD B2B değerlendirmesi"),
        ("GB_CORP", "Birleşik Krallık kurumsal B2B değerlendirmesi"),
        ("NO", "İletişim kurulmayacak"),
    ]
    email_basis = models.CharField(max_length=8, choices=EMAIL_BASIS, default="NONE")
    email_source_note = models.TextField(blank=True, default="")
    email_checked = models.BooleanField(default=False)
    outreach_approved_at = models.DateTimeField(null=True, blank=True)
    outreach_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, related_name="approved_export_prospects",
        on_delete=models.SET_NULL,
    )

    source = models.CharField(max_length=8, choices=SOURCE, default="MANUAL")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    last_contacted_at = models.DateTimeField(null=True, blank=True)
    next_followup_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return self.name


class SearchRun(models.Model):
    STATES = [("RUNNING", "Çalışıyor"), ("DONE", "Tamamlandı"), ("ERROR", "Hata")]
    run_date = models.DateField(unique=True)
    status = models.CharField(max_length=8, choices=STATES, default="RUNNING")
    created_count = models.PositiveIntegerField(default=0)
    searched_countries = models.CharField(max_length=120, blank=True, default="")
    error_message = models.CharField(max_length=300, blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-run_date",)


class SuppressedEmail(models.Model):
    """Global do-not-contact list, including unsubscribe and bounce requests."""
    email = models.EmailField(max_length=254, unique=True)
    reason = models.CharField(max_length=24, default="UNSUBSCRIBE")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class OutreachEmail(models.Model):
    KIND = [("INITIAL", "İlk tanıtım"), ("FOLLOWUP", "Tek takip")]
    STATES = [
        ("QUEUED", "Kuyrukta"), ("SENDING", "Gönderiliyor"),
        ("SENT", "Gönderildi"), ("FAILED", "Hata"),
        ("CANCELLED", "İptal"),
    ]
    prospect = models.ForeignKey(Prospect, on_delete=models.CASCADE, related_name="outreach_emails")
    kind = models.CharField(max_length=8, choices=KIND, default="INITIAL")
    email = models.EmailField(max_length=254)
    subject = models.CharField(max_length=180)
    body = models.TextField()
    status = models.CharField(max_length=12, choices=STATES, default="QUEUED", db_index=True)
    scheduled_at = models.DateTimeField(db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    error_message = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(fields=["prospect", "kind"], name="unique_export_message_kind")
        ]
