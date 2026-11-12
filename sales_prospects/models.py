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
    source_url = models.URLField(max_length=500, blank=True)
    canonical_url = models.CharField(max_length=500, unique=True)
    source_snippet = models.TextField(blank=True, default="")
    status = models.CharField(max_length=12, choices=STATUS, default="NEW", db_index=True)
    note = models.TextField(blank=True, default="")
    message_draft = models.TextField(blank=True, default="")
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
