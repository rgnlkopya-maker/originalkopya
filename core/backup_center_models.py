from django.db import models


class BackupPolicy(models.Model):
    MODULES = [("folios", "Sipariş Föyleri"), ("instruments", "Çek / Senet")]
    FREQUENCIES = [("daily", "Her gün"), ("weekly", "Haftalık"), ("off", "Kapalı")]
    module = models.CharField(max_length=20, unique=True, choices=MODULES)
    frequency = models.CharField(max_length=10, choices=FREQUENCIES, default="off")
    hour = models.PositiveSmallIntegerField(default=3)
    minute = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Yedekleme Kuralı"


class BackupExecution(models.Model):
    module = models.CharField(max_length=20, choices=BackupPolicy.MODULES)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    success = models.BooleanField(default=False)
    files = models.PositiveIntegerField(default=0)
    photos = models.PositiveIntegerField(default=0)
    records = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-started_at"]
