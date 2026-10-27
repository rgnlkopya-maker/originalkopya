import os
import uuid
import logging

logger = logging.getLogger(__name__)

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from supabase import create_client

from .instrument_models import NegotiableInstrument, InstrumentPhoto


def _allowed(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists())


def _storage(ensure_bucket=False):
    url = getattr(settings, "SUPABASE_URL", None)
    key = getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
    bucket_name = os.getenv("SUPABASE_INSTRUMENT_BUCKET", "moli-financial-documents")
    if not url or not key:
        raise RuntimeError("Supabase servis bağlantısı yapılandırılmamış.")
    client = create_client(url, key)
    if ensure_bucket:
        try:
            client.storage.get_bucket(bucket_name)
        except Exception as error:
            # Only create when the private bucket is genuinely missing.
            msg = str(error).lower()
            if not any(term in msg for term in ("not found", "does not exist", "404", "bucket not found")):
                raise
            try:
                client.storage.create_bucket(bucket_name, options={"public": False})
            except Exception:
                # Handle concurrent requests which may have created it already.
                client.storage.get_bucket(bucket_name)
    return client.storage.from_(bucket_name)


@login_required
@require_POST
def instrument_photo_upload(request, pk):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    instrument = get_object_or_404(NegotiableInstrument, pk=pk)
    side = request.POST.get("side")
    file = request.FILES.get("photo")
    if side not in ("FRONT", "BACK") or not file:
        messages.error(request, "Ön veya arka yüz fotoğrafı seçin.")
        return redirect("instrument_list")
    if file.size > 10 * 1024 * 1024 or file.size < 50:
        messages.error(request, "Fotoğraf 10 MB altında olmalı.")
        return redirect("instrument_list")
    from django.core.exceptions import ValidationError
    from core.upload_security import validate_image_upload
    try:
        ext, content_type = validate_image_upload(file)
        if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            raise ValidationError("JPG, PNG veya WEBP fotoğraf seçin.")
        file.seek(0)
        storage = _storage(ensure_bucket=True)
        code = f"CS-{instrument.pk:06d}"
        path = f"instrument-photos/{code}/{code}-{'ON' if side == 'FRONT' else 'ARKA'}-{uuid.uuid4().hex[:8]}{ext.lower()}"
        storage.upload(path, file.read(), file_options={"content-type": content_type, "upsert": "false"})
        old = InstrumentPhoto.objects.filter(instrument=instrument, side=side).first()
        try:
            InstrumentPhoto.objects.update_or_create(instrument=instrument, side=side, defaults={"storage_path":path,"original_name":file.name[:255]})
        except Exception:
            storage.remove([path])
            raise
        if old:
            try:
                storage.remove([old.storage_path])
            except Exception:
                pass
        messages.success(request, f"{code} {'ön' if side == 'FRONT' else 'arka'} yüz fotoğrafı kaydedildi.")
    except (ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    except Exception:
        logger.exception("Instrument photo upload failed for instrument %s", pk)
        messages.error(request, "Fotoğraf kaydedilemedi. Supabase özel depolama bağlantısını ve bucket yetkisini kontrol edin.")
    return redirect("instrument_list")


@login_required
def instrument_photo_view(request, pk, side):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    photo = get_object_or_404(InstrumentPhoto, instrument_id=pk, side=side.upper())
    try:
        response = _storage().create_signed_url(photo.storage_path, 60)
        signed = response.get("signedURL") or response.get("signedUrl") or response.get("signed_url")
        if not signed:
            return HttpResponseNotFound("Fotoğraf bağlantısı oluşturulamadı.")
        result = redirect(signed)
        result["Cache-Control"] = "private, no-store"
        return result
    except Exception:
        return HttpResponseNotFound("Fotoğraf görüntülenemedi.")
