"""Persisted Google Drive health checks; never write document contents or tokens to logs."""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .instrument_models import InstrumentDriveHealth
from .instrument_drive_oauth import connected, drive_service
from .instrument_backup_views import _check_parent

log = logging.getLogger(__name__)


def check_drive_health(force=False):
    now = timezone.now()
    with transaction.atomic():
        state, _ = InstrumentDriveHealth.objects.select_for_update().get_or_create(key=1)
        if not force and state.checked_at and now - state.checked_at < timedelta(hours=24):
            return state
        if not connected():
            state.status = "disconnected"
            state.message = "Google Drive hesabı bağlı değil. Yeniden bağlayın."
        else:
            try:
                _check_parent(drive_service())
            except Exception:
                log.warning("Google Drive health check failed (no credentials or contents logged)")
                state.status = "error"
                state.message = "Drive hesabı veya yedekleme klasörüne erişim sağlanamadı."
            else:
                state.status = "connected"
                state.message = "Google Drive yedekleme klasörü erişimi doğrulandı."
                state.last_success_at = now
        state.checked_at = now
        state.save(update_fields=["status", "message", "checked_at", "last_success_at"])
        return state
