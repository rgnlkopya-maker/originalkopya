"""Private photos attached to saved showroom folios; printing remains separate."""
import logging
import os
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from supabase import create_client

from app_settings.access import has_access
from core.upload_security import validate_image_upload
from .models import ShowroomDraft, ShowroomFolioPhoto
from .price_list_views import _can_manage

logger = logging.getLogger(__name__)


def _draft(request, pk):
    qs = ShowroomDraft.objects.filter(status__in=["PENDING", "APPROVED", "TRANSFERRED"])
    if not has_access(request.user, "can_view_folio_link"):
        qs = qs.filter(created_by=request.user)
    return get_object_or_404(qs, pk=pk)


def storage():
    url = getattr(settings, "SUPABASE_URL", None)
    key = getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
    if not url or not key:
        raise RuntimeError("Supabase credentials missing")
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
def upload(request, draft_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    draft = _draft(request, draft_id)
    files = request.FILES.getlist("photos")
    if not files:
        messages.error(request, "Fotoğraf seçilmedi.", extra_tags="folio_photo")
        return redirect("showroom_detail_page", draft_id=draft.pk)
    if len(files) > 15:
        messages.error(request, "Tek seferde en fazla 15 fotoğraf yükleyebilirsiniz.", extra_tags="folio_photo")
        return redirect("showroom_detail_page", draft_id=draft.pk)
    uploaded = 0
    for file in files:
        try:
            if not 50 <= file.size <= 10 * 1024 * 1024:
                raise ValueError("10 MB üstünde veya boş fotoğraf")
            ext, mime = validate_image_upload(file)
            if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                raise ValueError("Desteklenmeyen fotoğraf")
            file.seek(0)
            path = f"folio-source-photos/{draft.pk}/{uuid4().hex}{ext.lower()}"
            storage().upload(path, file.read(), file_options={"content-type": mime, "upsert": "false"})
            try:
                ShowroomFolioPhoto.objects.create(draft=draft, storage_path=path, original_name=file.name[:255])
            except Exception:
                storage().remove([path])
                raise
            uploaded += 1
        except Exception:
            logger.exception("Folio photo upload failed for folio %s", draft.pk)
            messages.error(request, "Bir fotoğraf yüklenemedi. Dosya biçimini ve bağlantıyı kontrol edin.", extra_tags="folio_photo")
    if uploaded:
        messages.success(request, f"{uploaded} fotoğraf kaydedildi.", extra_tags="folio_photo")
    return redirect("showroom_detail_page", draft_id=draft.pk)


@login_required
def view(request, draft_id, photo_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    _draft(request, draft_id)
    photo = get_object_or_404(ShowroomFolioPhoto, pk=photo_id, draft_id=draft_id)
    try:
        res = storage().create_signed_url(photo.storage_path, 120)
        url = res.get("signedURL") or res.get("signedUrl") or res.get("signed_url")
        if not url:
            raise ValueError("Missing URL")
        response = redirect(url)
        response["Cache-Control"] = "private, no-store"
        return response
    except Exception:
        logger.exception("Folio photo download failed")
        return HttpResponseNotFound("Fotoğraf görüntülenemedi.")


@login_required
@require_POST
def delete(request, draft_id, photo_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    _draft(request, draft_id)
    photo = get_object_or_404(ShowroomFolioPhoto, pk=photo_id, draft_id=draft_id)
    try:
        storage().remove([photo.storage_path])
        photo.delete()
        messages.success(request, "Fotoğraf kaldırıldı.", extra_tags="folio_photo")
    except Exception:
        logger.exception("Folio photo delete failed")
        messages.error(request, "Fotoğraf silinemedi.", extra_tags="folio_photo")
    return redirect("showroom_detail_page", draft_id=draft_id)
