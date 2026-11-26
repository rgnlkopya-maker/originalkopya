"""Private, server-proxied document archive. Never issue a public or signed URL."""
import logging
import re
import unicodedata
from functools import wraps
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import content_disposition_header
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe, require_POST
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener
from app_settings.access import has_full_access
from storage3.exceptions import StorageApiError
from supabase import create_client

from .document_archive_models import ArchiveDocument, ArchiveFolder

log = logging.getLogger(__name__)
BUCKET = "moli-evrak-arsivi"
MAX_BYTES = 12 * 1024 * 1024
MAX_BATCH = 8
MAX_PIXELS = 32_000_000
FORMATS = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp")}
CONTENT_TYPES = {"application/pdf", *(mime for _, mime in FORMATS.values())}
register_heif_opener()


def can_access_archive(user):
    return user.is_authenticated and user.is_active and has_full_access(user)


def archive_only(view):
    @never_cache
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not can_access_archive(request.user):
            return HttpResponseForbidden("Evrak Arşivi yalnızca patron ve müdür hesaplarına açıktır.")
        return view(request, *args, **kwargs)
    return wrapped


def _private_storage(create=False):
    if not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY):
        raise RuntimeError("Archive storage credentials are unavailable")
    storage = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY).storage
    try:
        bucket = storage.get_bucket(BUCKET)
    except StorageApiError as exc:
        status = str(getattr(exc, "status", "") or getattr(exc, "code", ""))
        if not create or (status not in {"404", "NoSuchBucket"} and "bucket not found" not in str(exc).lower()):
            raise
        try:
            storage.create_bucket(BUCKET, options={
                "public": False,
                "file_size_limit": MAX_BYTES,
                "allowed_mime_types": sorted(CONTENT_TYPES),
            })
        except StorageApiError:
            # Another request may have created it; always confirm privacy below.
            pass
        bucket = storage.get_bucket(BUCKET)
    if bucket.public is not False:
        raise RuntimeError("Archive bucket is not verified private")
    return storage.from_(BUCKET)


def _clean_name(value, limit):
    value = unicodedata.normalize("NFC", value or "")
    value = " ".join("".join(c for c in value if unicodedata.category(c)[0] != "C").split())
    return value[:limit].strip()


def _normalize_file(upload):
    if not 0 < upload.size <= MAX_BYTES:
        raise ValidationError("Her evrak en fazla 12 MB olabilir.")
    raw = upload.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValidationError("Her evrak en fazla 12 MB olabilir.")
    if re.match(rb"^%PDF-(?:1\.[0-7]|2\.0)(?:\r|\n)", raw):
        if not raw.rstrip(b" \r\n\t").endswith(b"%%EOF"):
            raise ValidationError("PDF eksik veya bozuk görünüyor.")
        return raw, "pdf", "application/pdf"

    try:
        with Image.open(BytesIO(raw)) as image:
            kind = image.format
            if kind not in {*FORMATS, "HEIF", "HEIC"}:
                raise ValidationError("Yalnızca PDF, JPG, PNG, WEBP veya HEIC yüklenebilir.")
            if image.width * image.height > MAX_PIXELS:
                raise ValidationError("Fotoğraf çok büyük. Daha düşük çözünürlükle yeniden çekin.")
            if getattr(image, "n_frames", 1) != 1:
                raise ValidationError("Hareketli görseller yüklenemez.")
            if kind in {"HEIF", "HEIC"}:
                out = BytesIO()
                ImageOps.exif_transpose(image).convert("RGB").save(out, format="JPEG", quality=92)
                raw = out.getvalue()
                kind = "JPEG"
            else:
                image.verify()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValidationError("Dosya okunamadı. PDF veya desteklenen bir fotoğraf seçin.") from exc
    if len(raw) > MAX_BYTES:
        raise ValidationError("Dönüştürülen fotoğraf 12 MB sınırını aşıyor.")
    ext, mime = FORMATS[kind]
    return raw, ext, mime


def _folder(folder_id):
    return get_object_or_404(ArchiveFolder, pk=folder_id) if folder_id else None


def _back(folder):
    if folder:
        return redirect("document_archive_folder", folder_id=folder.pk)
    return redirect("document_archive")


@archive_only
@require_safe
def archive_index(request, folder_id=None):
    folder = _folder(folder_id)
    path = []
    item = folder
    while item:
        path.append(item)
        item = item.parent
    path.reverse()
    return render(request, "core/document_archive.html", {
        "folder": folder,
        "breadcrumbs": path,
        "folders": ArchiveFolder.objects.filter(parent=folder),
        "documents": ArchiveDocument.objects.filter(folder=folder),
    })


@archive_only
@require_POST
def archive_create_folder(request, folder_id=None):
    parent = _folder(folder_id)
    name = _clean_name(request.POST.get("name"), 120)
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        messages.error(request, "Geçerli bir klasör adı girin.")
    else:
        try:
            with transaction.atomic():
                ArchiveFolder.objects.create(parent=parent, name=name, name_key=name.casefold()[:240])
        except IntegrityError:
            messages.error(request, "Bu konumda aynı isimde bir klasör var.")
        else:
            messages.success(request, "Klasör oluşturuldu.")
    return _back(parent)


@archive_only
@require_POST
def archive_upload(request, folder_id=None):
    folder = _folder(folder_id)
    files = request.FILES.getlist("documents")
    if not files or len(files) > MAX_BATCH:
        messages.error(request, "Bir seferde 1 ile 8 arasında evrak seçin.")
        return _back(folder)
    title = _clean_name(request.POST.get("title"), 150)
    storage = None
    saved = 0
    for upload in files:
        original = _clean_name(upload.name, 170) or "Evrak"
        try:
            raw, ext, mime = _normalize_file(upload)
        except ValidationError as exc:
            messages.error(request, f"{original}: {exc.messages[0]}")
            continue
        base = original.rsplit(".", 1)[0].strip() if "." in original else original
        if title and len(files) == 1:
            base = title
        base = base.replace("/", "-").replace(chr(92), "-")
        record = ArchiveDocument(
            folder=folder, name=f"{base or 'Evrak'}.{ext}", content_type=mime,
            byte_size=len(raw), uploaded_by=request.user,
        )
        try:
            if storage is None:
                storage = _private_storage(create=True)
            storage.upload(record.storage_path, raw, file_options={
                "content-type": mime, "cache-control": "0", "upsert": "false",
            })
            try:
                record.save(force_insert=True)
            except Exception:
                try:
                    storage.remove([record.storage_path])
                except Exception:
                    log.warning("Archive orphan cleanup failed: %s", record.pk)
                raise
            saved += 1
        except Exception:
            # Avoid putting filenames, object bytes or credentials into logs.
            log.warning("Archive upload could not be saved: %s", record.pk)
            messages.error(request, f"{original}: kaydedilemedi. Tekrar deneyin.")
    if saved:
        messages.success(request, f"{saved} evrak kaydedildi.")
    return _back(folder)


@archive_only
@require_safe
def archive_file(request, document_id):
    document = get_object_or_404(ArchiveDocument, pk=document_id)
    if document.content_type not in CONTENT_TYPES:
        return HttpResponse("Evrak türü desteklenmiyor.", status=415)
    try:
        raw = _private_storage().download(document.storage_path)
        if len(raw) != document.byte_size:
            raise ValueError("Archive size mismatch")
    except Exception:
        log.warning("Archive item could not be retrieved: %s", document.pk)
        return HttpResponse("Evrak şu anda açılamadı. Daha sonra tekrar deneyin.", status=503)
    is_attachment = document.content_type == "application/pdf" or request.GET.get("download") == "1"
    response = HttpResponse(raw, content_type=document.content_type)
    response["Content-Disposition"] = content_disposition_header(is_attachment, document.name)
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    response["X-Content-Type-Options"] = "nosniff"
    response["Referrer-Policy"] = "no-referrer"
    return response
