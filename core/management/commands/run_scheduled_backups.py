"""Scheduled backups use the existing, tested upload views and stored module policies."""
import logging
from datetime import datetime, timedelta
from types import SimpleNamespace

from django.core.management.base import BaseCommand
from django.db import transaction
from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from django.utils import timezone

from core.backup_center_models import BackupPolicy, BackupExecution
from core.instrument_backup_views import instrument_backup
from core.instrument_models import InstrumentBackupRun
from product_cards.showroom_backup_views import backup as folio_backup

logger = logging.getLogger(__name__)


def _request(path, data):
    request = RequestFactory().post(path, data)
    request.user = SimpleNamespace(is_authenticated=True, is_superuser=True)
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def run_module(module):
    if module == "folios":
        next_id = 0
        count = files = photos = 0
        while True:
            response = folio_backup(_request("/urun-kartlari/showroom-foyu/yedekle/", {
                "incremental": "1", "draft_id": str(next_id)
            }))
            if response.status_code != 200:
                raise RuntimeError("Föy yedekleme isteği başarısız oldu.")
            import json
            data = json.loads(response.content)
            if not data.get("ok"):
                raise RuntimeError(data.get("message", "Föy yedeği başarısız."))
            count += data["folios"]
            files += data["files"]
            photos += data["photos"]
            if data["done"]:
                return count, files, photos
            if data["next_id"] <= next_id:
                raise RuntimeError("Föy yedeği ilerlemiyor.")
            next_id = data["next_id"]
    if module == "instruments":
        response = instrument_backup(_request("/muhasebe/cek-senet/yedekle/", {}))
        record = InstrumentBackupRun.objects.order_by("-id").first()
        if not record or not record.success:
            raise RuntimeError("Çek/Senet yedeği başarısız oldu.")
        return record.record_count, 2, record.new_photo_count
    raise ValueError("Desteklenmeyen modül")


class Command(BaseCommand):
    help = "Run due module backup schedules (Europe/Istanbul). Execute every minute via Render cron."

    def handle(self, *args, **options):
        now = timezone.localtime()
        for module, _ in BackupPolicy.MODULES:
            with transaction.atomic():
                policy = BackupPolicy.objects.select_for_update().filter(module=module).first()
                if not policy or policy.frequency == "off":
                    continue
                scheduled = now.replace(hour=policy.hour, minute=policy.minute, second=0, microsecond=0)
                if now < scheduled:
                    continue
                if policy.frequency == "weekly" and now.weekday() != 6:
                    continue
                # Claim once per scheduled calendar date. A failed run is visible
                # in the history rather than silently being retried indefinitely.
                if BackupExecution.objects.filter(module=module, started_at__date=now.date()).exists():
                    continue
                run = BackupExecution.objects.create(module=module)
            try:
                count, files, photos = run_module(module)
                run.records = count
                run.files = files
                run.photos = photos
                run.success = True
                run.message = "Yedekleme tamamlandı."
            except Exception:
                logger.exception("Scheduled backup failed: %s", module)
                run.message = "Yedekleme başarısız; Render loglarını kontrol edin."
            run.completed_at = timezone.now()
            run.save(update_fields=["records", "files", "photos", "success", "message", "completed_at"])
            self.stdout.write(f"{module}: {'OK' if run.success else 'FAILED'}")
