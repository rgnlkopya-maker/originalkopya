"""Private photos attached to saved showroom folios; printing remains separate."""
import logging
import os
import io
from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.exceptions import ValidationError
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

# Camera formats are detected from actual bytes, not client-supplied extensions.
SUPPORTED_PHOTO_FORMATS = frozenset(("JPEG", "PNG", "WEBP", "HEIF", "HEIC", "TIFF", "BMP", "GIF", "AVIF", "MPO"))


def _photo_format(file):
    """Best-effort format label for diagnostics, without storing photo contents."""
    try:
        file.seek(0)
        with Image.open(file) as image:
            return (image.format or "UNKNOWN").upper()
    except (UnidentifiedImageError, OSError, ValueError):
        return "UNKNOWN"
    finally:
        file.seek(0)


def _prepare_photo(file):
    if file.size > 20 * 1024 * 1024:
        raise ValidationError("Fotoğraf 20 MB sınırını aşıyor.")
    if file.size < 50:
        raise ValidationError("Dosya boş veya geçerli bir fotoğraf içermiyor.")
    try:
        file.seek(0)
        try:
            ext, mime = validate_image_upload(file)
            return ext, mime, file.read()
        except ValidationError:
            file.seek(0)
        from pillow_heif import register_heif_opener
        register_heif_opener()
        with Image.open(file) as image:
            detected = (image.format or "UNKNOWN").upper()
            if detected not in SUPPORTED_PHOTO_FORMATS:
                raise ValidationError(f"Desteklenmeyen fotoğraf biçimi: {detected}.")
            image.verify()
        file.seek(0)
        with Image.open(file) as image:
            image.seek(0)
            converted = ImageOps.exif_transpose(image).convert("RGB")
            output = io.BytesIO()
            converted.save(output, format="JPEG", quality=88, optimize=True)
            return ".jpg", "image/jpeg", output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("Dosya geçerli bir fotoğraf olarak okunamadı.") from exc
    finally:
        file.seek(0)


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
            ext, mime, contents = _prepare_photo(file)
            path = f"folio-source-photos/{draft.pk}/{uuid4().hex}{ext.lower()}"
            storage().upload(path, contents, file_options={"content-type": mime, "upsert": "false"})
            try:
                ShowroomFolioPhoto.objects.create(draft=draft, storage_path=path, original_name=file.name[:255])
            except Exception:
                storage().remove([path])
                raise
            uploaded += 1
        except ValidationError as exc:
            detected = _photo_format(file)
            reason = "; ".join(exc.messages)
            logger.warning(
                "Folio photo rejected: folio=%s filename=%r size_bytes=%s client_mime=%s detected_format=%s reason=%s",
                draft.pk, file.name, file.size, file.content_type, detected, reason,
            )
            messages.error(
                request,
                f"{file.name}: {reason} (Algılanan biçim: {detected}; dosya türü: {file.content_type or 'bilinmiyor'}).",
                extra_tags="folio_photo",
            )
        except Exception:
            logger.exception(
                "Folio photo upload failed: folio=%s filename=%r size_bytes=%s client_mime=%s detected_format=%s",
                draft.pk, file.name, file.size, file.content_type, _photo_format(file),
            )
            messages.error(request, f"{file.name}: Dosya doğrulandı ancak yükleme veya kayıt sırasında hata oluştu.", extra_tags="folio_photo")
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
