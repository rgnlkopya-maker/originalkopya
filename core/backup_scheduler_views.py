"""Authenticated scheduler tick. Credentials remain on the existing MoliApp web service."""
import hmac
import json
import logging
import os
from datetime import timedelta
from types import SimpleNamespace

from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import transaction
from django.http import JsonResponse
from django.test import RequestFactory
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .backup_center_models import BackupPolicy, BackupExecution
from .instrument_backup_views import instrument_backup
from .instrument_models import InstrumentBackupRun
from product_cards.showroom_backup_views import backup as folio_backup

logger = logging.getLogger(__name__)

def _internal_request(path, data):
    request = RequestFactory().post(path, data)
    request.user = SimpleNamespace(is_authenticated=True, is_superuser=True)
    request.session = {}
    request._messages = FallbackStorage(request)
    return request

@csrf_exempt
@require_POST
def scheduler_tick(request):
    secret = os.environ.get("MOLI_BACKUP_TICK_SECRET", "")
    supplied = request.headers.get("X-Moli-Backup-Key", "")
    if not secret or not hmac.compare_digest(secret, supplied):
        return JsonResponse({"error": "forbidden"}, status=403)
    # This already-running minute scheduler also delivers due reminders and
    # to-do push alarms. Both processors keep their own interval/idempotency
    # state so repeated ticks never trigger an immediate duplicate.
    for label, processor in (
        ("reminders", "process_due_reminders"),
        ("todos", "process_due_todos"),
    ):
        try:
            if label == "reminders":
                from .reminder_service import process_due_reminders
                result = process_due_reminders()
            else:
                from .todo_service import process_due_todos
                result = process_due_todos()
            logger.info("Scheduled %s processed: %s", label, result)
        except Exception:
            logger.exception("Scheduled %s processing failed", label)

    # Existing once-per-minute secure tick drives customer alerts too.
    # Status transitions are evaluated after 09:00 and leader changes after
    # 20:00 Istanbul time; persistent DB snapshots prevent duplicate sends.
    try:
        from .customer_monitor_service import process_customer_monitor
        customer_monitor_result = process_customer_monitor()
        logger.info("Scheduled customer monitor: %s", customer_monitor_result)
    except Exception:
        logger.exception("Scheduled customer monitor failed")

    # Daily product rankings: 20:00 Istanbul; persistent DB snapshot prevents
    # duplicate notifications on concurrent or repeated minute ticks.
    try:
        from .product_monitor_service import process_product_monitor
        product_monitor_result = process_product_monitor()
        logger.info("Scheduled product monitor: %s", product_monitor_result)
    except Exception:
        logger.exception("Scheduled product monitor failed")

    # Independent finance integrity audit. No daily 20:00 summary:
    # only newly detected financial data errors generate notifications.
    # The audit enforces its own five-minute check and persistent deduplication.
    try:
        from .finance_integrity_monitor import process_finance_integrity
        result = process_finance_integrity()
        logger.info("Finance integrity: %s", result)
    except Exception:
        logger.exception("Scheduled finance integrity audit failed")

    # Prospect discovery is now manager-guided using Google browser searches.
    # Do not run the old automatic Brave prospect discovery schedule.

    # Discover publicly displayed phone, WhatsApp and Instagram business links
    # for at most one previously unscanned shop per scheduled tick. This never
    # sends messages and never fetches private/social-network profile pages.
    try:
        from sales_prospects.contact_enrichment import scan_one_pending_prospect
        contact_result = scan_one_pending_prospect()
        if contact_result.get("status") == "DONE":
            logger.info("Shop contact enrichment: %s", contact_result)
    except Exception:
        logger.exception("Shop contact enrichment failed")

    # Export sales email automation is OFF by default. Never send unless a
    # manager has approved a contact and sender credentials + compliance gates
    # are all explicitly configured in Render.
    try:
        from sales_prospects.outreach import process_outreach_queue
        outreach_result = process_outreach_queue()
        if outreach_result.get("sent"):
            logger.info("Approved export sales emails sent: %s", outreach_result["sent"])
    except Exception:
        logger.exception("Approved export sales email dispatch failed")

    now = timezone.localtime()
    outcomes = []
    for module, _ in BackupPolicy.MODULES:
        try:
            policy = BackupPolicy.objects.filter(module=module).first()
            if not policy or policy.frequency == "off":
                continue
            scheduled = now.replace(hour=policy.hour, minute=policy.minute, second=0, microsecond=0)
            if now < scheduled or (policy.frequency == "weekly" and now.weekday() != 6) or (policy.frequency == "monthly" and now.day != 10):
                continue
            if module == "salary":
                from .salary_backup_service import salary_backup
                existing = BackupExecution.objects.filter(module="salary", success=True, started_at__year=now.year, started_at__month=now.month).exists()
                if existing:
                    continue
                result = salary_backup()
                BackupExecution.objects.create(module="salary", completed_at=timezone.now(), success=True, files=len(result["files"]), records=result["records"], message="Şifreli maaş yedeği Drive'a kaydedildi", details=result["files"])
                outcomes.append({"module": "salary", "done": True})
                continue
            if module == "database":
                from django.core.management import call_command
                call_command("backup_full_database")
                outcomes.append({"module": "database", "triggered": True})
                continue
            with transaction.atomic():
                run = BackupExecution.objects.select_for_update().filter(module=module, started_at__date=now.date()).order_by("-id").first()
                if run and run.completed_at:
                    # An updated schedule is a new instruction, even if an
                    # earlier schedule already completed on the same day.
                    if run.started_at >= policy.updated_at:
                        continue
                    run = None
                if not run:
                    run = BackupExecution.objects.create(module=module, message="Yedekleme sürüyor")
            if module == "folios":
                response = folio_backup(_internal_request("/urun-kartlari/showroom-foyu/yedekle/", {"incremental": "1", "draft_id": str(run.cursor)}))
                if response.status_code != 200:
                    raise RuntimeError("Föy yedekleme isteği başarısız.")
                payload = json.loads(response.content)
                if not payload.get("ok") or (not payload["done"] and payload["next_id"] <= run.cursor):
                    raise RuntimeError("Föy yedekleme ilerleyemedi.")
                run.details = (run.details or []) + payload.get("details", [])
                run.records += payload["folios"]
                run.files += payload["files"]
                run.photos += payload["photos"]
                run.cursor = payload["next_id"]
                if payload["done"]:
                    run.completed_at = timezone.now()
                    run.success = True
                    run.message = "Tamamlandı"
            else:
                previous = InstrumentBackupRun.objects.order_by("-id").values_list("id", flat=True).first() or 0
                instrument_backup(_internal_request("/muhasebe/cek-senet/yedekle/", {}))
                source = InstrumentBackupRun.objects.filter(id__gt=previous).order_by("-id").first()
                if not source or not source.success:
                    raise RuntimeError("Çek/Senet yedeği tamamlanamadı.")
                run.records = source.record_count
                run.photos = source.new_photo_count
                run.files = 2
                run.details = [{"summary": "Her çalışmada yeni Excel ve JSON dosyası oluşturuldu.", "records": source.record_count, "new_photos": source.new_photo_count, "comparison": "Kayıt bazında önceki yedekle karşılaştırma henüz yapılmıyor."}]
                run.success = True
                run.completed_at = timezone.now()
                run.message = "Tamamlandı"
            run.save()
            outcomes.append({"module": module, "done": bool(run.completed_at), "records": run.records})
        except Exception:
            logger.exception("Scheduled backup failed: %s", module)
            if module in ("database", "salary"):
                outcomes.append({"module": module, "error": True})
                continue
            if "run" in locals() and run.module == module:
                run.completed_at = timezone.now()
                run.success = False
                run.message = "Hata; Render loglarını kontrol edin"
                run.save(update_fields=["completed_at", "success", "message"])
            outcomes.append({"module": module, "error": True})
    return JsonResponse({"ok": True, "outcomes": outcomes})
