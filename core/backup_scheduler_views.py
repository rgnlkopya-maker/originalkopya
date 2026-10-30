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
    now = timezone.localtime()
    outcomes = []
    for module, _ in BackupPolicy.MODULES:
        try:
            policy = BackupPolicy.objects.filter(module=module).first()
            if not policy or policy.frequency == "off":
                continue
            scheduled = now.replace(hour=policy.hour, minute=policy.minute, second=0, microsecond=0)
            if now < scheduled or (policy.frequency == "weekly" and now.weekday() != 6):
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
                run.success = True
                run.completed_at = timezone.now()
                run.message = "Tamamlandı"
            run.save()
            outcomes.append({"module": module, "done": bool(run.completed_at), "records": run.records})
        except Exception:
            logger.exception("Scheduled backup failed: %s", module)
            if "run" in locals() and run.module == module:
                run.completed_at = timezone.now()
                run.success = False
                run.message = "Hata; Render loglarını kontrol edin"
                run.save(update_fields=["completed_at", "success", "message"])
            outcomes.append({"module": module, "error": True})
    return JsonResponse({"ok": True, "outcomes": outcomes})
