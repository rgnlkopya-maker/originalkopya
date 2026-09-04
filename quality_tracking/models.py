from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import Order


class QualityIssue(models.Model):
    STAGE_CHOICES = [
        ("GENEL", "Genel"),
        ("MALZEME", "Malzeme"),
        ("KESIM", "Kesim"),
        ("DIKIM", "Dikim"),
        ("NAKIS", "Nakış"),
        ("SUSLEME", "Süsleme"),
        ("HAZIR", "Hazır"),
        ("SEVKIYAT", "Sevkiyat"),
    ]

    STATUS_CHOICES = [
        ("ACIK", "Açık"),
        ("COZULDU", "Çözüldü"),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="quality_issues")
    konu = models.CharField(max_length=180)
    aciklama = models.TextField()
    asama = models.CharField(max_length=20, choices=STAGE_CHOICES, default="GENEL")
    sorumlu_personeller = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="quality_issues",
    )
    durum = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ACIK", db_index=True)
    cozum_notu = models.TextField(blank=True, default="")
    kaydeden = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_quality_issues",
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["order", "durum"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.order.siparis_numarasi} - {self.konu}"
