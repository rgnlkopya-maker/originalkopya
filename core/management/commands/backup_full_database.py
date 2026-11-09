"""Daily full encrypted PostgreSQL backup, run in a separate process."""
import logging
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from core.backup_center_models import BackupExecution
from scripts.full_db_drive_backup_draft import run_backup

log = logging.getLogger(__name__)
LOCK_ID = 687123456123

class Command(BaseCommand):
    help = "Back up PostgreSQL database encrypted to Google Drive"

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", [LOCK_ID])
            locked = cursor.fetchone()[0]
        if not locked:
            return
        try:
            today = timezone.localtime().date()
            if BackupExecution.objects.filter(module="database", started_at__date=today, success=True).exists():
                return
            run = BackupExecution.objects.create(module="database", message="Tam yedek sürüyor")
            try:
                result = run_backup()
                run.success = True
                run.files = 1
                run.message = "Google Drive'a şifreli tam yedek kaydedildi"
                run.details = [{"drive_file_id": result["id"], "bytes": result["bytes"]}]
            except Exception:
                run.success = False
                run.message = "Tam veritabanı yedeği başarısız; Render loglarını kontrol edin"
                log.exception("Full database backup failed")
            finally:
                run.completed_at = timezone.now()
                run.save()
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [LOCK_ID])
