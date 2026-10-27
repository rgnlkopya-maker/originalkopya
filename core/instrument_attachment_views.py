"""Private check attachment storage, restricted to accounting managers."""
import logging
import os
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from supabase import create_client

from .instrument_models import InstrumentAttachment, NegotiableInstrument
from core.upload_security import validate_image_upload

logger = logging.getLogger(__name__)


def allowed(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists())


def storage():
    url = getattr(settings, "SUPABASE_URL", None)
    key = getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
    if not url or not key:
        raise RuntimeError("Supabase service credentials are missing.")
    client = create_client(url, key)
    bucket = os.getenv("SUPABASE_INSTRUMENT_BUCKET", "moli-financial-documents")
    try:
        client.storage.get_bucket(bucket)
    except Exception as exc:
        if not any(x in str(exc).lower() for x in ("not found", "does not exist", "404")):
            raise
        try:
            client.storage.create_bucket(bucket, options={"public": False})
        except Exception:
            client.storage.get_bucket(bucket)
    return client.storage.from_(bucket)


@login_required
@require_POST
def attachment_upload(request, pk):
    if not allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    get_object_or_404(NegotiableInstrument, pk=pk)
    file = request.FILES.get("photo")
    if file is None:
        messages.error(request, "Fotoğraf seçin.")
        return redirect("instrument_detail", pk=pk)
    try:
        if not 50 <= file.size <= 10 * 1024 * 1024:
            raise ValueError("Fotoğraf 10 MB altında olmalı.")
        ext, content_type = validate_image_upload(file)
        if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            raise ValueError("JPG, PNG veya WEBP yükleyin.")
        file.seek(0)
        data = file.read()
        client = storage()
        with transaction.atomic():
            record = NegotiableInstrument.objects.select_for_update().get(pk=pk)
            sequence = record.next_photo_sequence
            filename = f"{record.pk}-{sequence}{ext.lower()}"
            # Use private per-check folder and stable numbered filename.
            path = f"instrument-photos/{record.pk}/{filename}"
            client.upload(path, data, file_options={"content-type": content_type, "upsert": "false"})
            try:
                InstrumentAttachment.objects.create(instrument=record, sequence=sequence, storage_path=path, original_name=file.name[:255])
                record.next_photo_sequence = sequence + 1
                record.save(update_fields=["next_photo_sequence"])
            except Exception:
                client.remove([path])
                raise
        messages.success(request, f"{filename} yüklendi.")
    except Exception as exc:
        logger.exception("Check attachment upload failed: %s", pk)
        messages.error(request, "Fotoğraf yüklenemedi. Dosyayı ve özel depolama bağlantısını kontrol edin.")
    return redirect("instrument_detail", pk=pk)


@login_required
def attachment_view(request, pk, attachment_id):
    if not allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    photo = get_object_or_404(InstrumentAttachment, id=attachment_id, instrument_id=pk)
    try:
        res = storage().create_signed_url(photo.storage_path, 60)
        url = res.get("signedURL") or res.get("signedUrl") or res.get("signed_url")
        if not url:
            raise ValueError("No signed URL")
        response = redirect(url)
        response["Cache-Control"] = "private, no-store"
        return response
    except Exception:
        logger.exception("Check attachment view failed: %s", attachment_id)
        return HttpResponseNotFound("Fotoğraf görüntülenemedi.")


@login_required
@require_POST
def attachment_delete(request, pk, attachment_id):
    if not allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    photo = get_object_or_404(InstrumentAttachment, id=attachment_id, instrument_id=pk)
    try:
        storage().remove([photo.storage_path])
        photo.delete()
        messages.success(request, "Fotoğraf silindi.")
    except Exception:
        logger.exception("Check attachment deletion failed: %s", attachment_id)
        messages.error(request, "Fotoğraf silinemedi.")
    return redirect("instrument_detail", pk=pk)
