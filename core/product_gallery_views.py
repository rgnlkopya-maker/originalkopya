import os
import logging
import json
from io import BytesIO
from uuid import uuid4
from functools import lru_cache
from django.db import IntegrityError, transaction
from django.conf import settings
from django.core.cache import cache
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from core.models import GalleryAlbum, GalleryGroup, GalleryMedia, UrunKod, URUN_TIPI_CHOICES
from supabase import create_client

def _allowed(user):
    return bool(user and user.is_authenticated and user.is_active)

@lru_cache(maxsize=1)
def _bucket():
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Görsel depolama ayarları eksik.")
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    name = os.getenv("SUPABASE_GALLERY_BUCKET", "moli-product-gallery")
    return client.storage.from_(name)

@login_required
def product_gallery(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Ürün Albümü erişim yetkiniz yok.")
    from django.core.paginator import Paginator
    from django.db.models import OuterRef, Subquery
    from django.db.models.functions import Lower
    from django.db.models import Prefetch

    selected = None
    albums = []
    page_obj = None
    search_query = (request.GET.get("q") or "").strip()[:80]
    album_id = request.GET.get("album", "")
    if album_id.isdigit():
        selected = GalleryAlbum.objects.filter(pk=album_id).first()
    if selected:
        GalleryGroup.objects.get_or_create(album=selected, name="Standart Model")
        selected = GalleryAlbum.objects.prefetch_related(
            Prefetch("groups", queryset=GalleryGroup.objects.prefetch_related(
                Prefetch("media", queryset=GalleryMedia.objects.order_by("sort_order", "pk"))
            ))
        ).get(pk=selected.pk)
    else:
        cover_media = GalleryMedia.objects.filter(
            group__album_id=OuterRef("pk")
        ).order_by("-is_cover", "sort_order", "pk")
        queryset = GalleryAlbum.objects.annotate(
            cover_media_id=Subquery(cover_media.values("pk")[:1]),
            cover_media_type=Subquery(cover_media.values("content_type")[:1]),
        )
        if search_query:
            queryset = queryset.filter(code__icontains=search_query)
        queryset = queryset.order_by(Lower("code"), "pk")
        page_obj = Paginator(queryset, 24).get_page(request.GET.get("page"))
        albums = list(page_obj.object_list)
    return render(request, "core/product_gallery.html", {
        "albums": albums, "selected": selected, "page_obj": page_obj,
        "search_query": search_query,
        "products": UrunKod.objects.filter(aktif=True).order_by("kod"),
        "product_types": URUN_TIPI_CHOICES,
        "urun_tipi_secenekleri": URUN_TIPI_CHOICES,
        "aktif_urun_kodlari": UrunKod.objects.filter(aktif=True).order_by("kod"),
    })

@login_required
@require_POST
def create_album(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    product = UrunKod.objects.filter(pk=request.POST.get("product_id"), aktif=True).first() if request.POST.get("product_id", "").isdigit() else None
    if product is None:
        messages.error(request, "Lütfen mevcut ürün listesinden bir ürün seçin.")
        return redirect("product_gallery")
    code = product.kod
    album, created = GalleryAlbum.objects.get_or_create(code=code)
    messages.success(request, "Albüm oluşturuldu." if created else "Bu ürün kodunun albümü zaten mevcut.")
    return redirect("/urun-albumu/?album=" + str(album.pk))

@login_required
@require_POST
def create_group(request, album_id):
    logger = logging.getLogger(__name__)
    try:
        if not _allowed(request.user):
            return HttpResponseForbidden("Yetkiniz yok.")
        album = get_object_or_404(GalleryAlbum, pk=album_id)
        name = " ".join(request.POST.get("name", "").split())
        if not name or len(name) > 160:
            messages.error(request, "Lütfen geçerli bir müşteri adı girin.")
            return redirect("/urun-albumu/?album=" + str(album.pk))
        group, created = GalleryGroup.objects.get_or_create(album=album, name=name)
        messages.success(request, "Müşteri sekmesi oluşturuldu." if created else "Bu müşteri sekmesi zaten mevcut.")
        return redirect("/urun-albumu/?album=" + str(album.pk) + "&group=" + str(group.pk))
    except Exception:
        logger.exception("GALLERY_CREATE_GROUP_FAILURE album_id=%s", album_id)
        try:
            messages.error(request, "Müşteri sekmesi oluşturulamadı. Hata kaydedildi.")
        except Exception:
            pass
        return redirect("/urun-albumu/?album=" + str(album_id))

@login_required
@require_POST
def upload_media(request, group_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    group = get_object_or_404(GalleryGroup, pk=group_id)
    files = request.FILES.getlist("media")
    if not files or len(files) > 15:
        messages.error(request, "Bir seferde 1-15 fotoğraf veya video seçin.")
        return redirect("/urun-albumu/?album=" + str(group.album_id) + "&group=" + str(group.pk))
    from concurrent.futures import ThreadPoolExecutor
    from PIL import Image, UnidentifiedImageError, ImageOps

    def process_file(item):
        index, f = item
        if f.size > 100 * 1024 * 1024 or f.size == 0:
            return index, f.name, None, "Dosya boyutu geçersiz (en fazla 100 MB)."
        try:
            f.seek(0)
            signature = f.read(16)
            f.seek(0)
            mime = None
            try:
                with Image.open(f) as img:
                    img.verify()
                mime = "image/jpeg" if signature.startswith(bytes.fromhex("ffd8ff")) else ("image/png" if signature.startswith(bytes.fromhex("89504e47")) else ("image/webp" if signature.startswith(b"RIFF") and signature[8:12] == b"WEBP" else None))
            except (UnidentifiedImageError, OSError, ValueError):
                pass
            if mime is None and len(signature) >= 12 and signature[4:8] == b"ftyp" and signature[8:12] in (b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"qt  "):
                mime = "video/mp4"
            if not mime:
                return index, f.name, None, "Desteklenen türler JPG, PNG, WEBP ve MP4."
            ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "video/mp4": ".mp4"}[mime]
            path = f"gallery/{group.album_id}/{uuid4().hex}{ext}"
            f.seek(0)
            original = f.read()
            thumbnail_bytes = None
            if mime.startswith("image/"):
                try:
                    with Image.open(BytesIO(original)) as source:
                        preview = ImageOps.exif_transpose(source)
                        preview.thumbnail((600, 800))
                        if preview.mode != "RGB":
                            preview = preview.convert("RGB")
                        output = BytesIO()
                        preview.save(output, format="JPEG", quality=78, optimize=True)
                        thumbnail_bytes = output.getvalue()
                except Exception:
                    logging.getLogger(__name__).exception("GALLERY_THUMBNAIL_FAILURE path=%s", path)
            _bucket().upload(path, original, file_options={"content-type": mime, "upsert": "false"})
            thumbnail_path = ""
            if thumbnail_bytes:
                try:
                    thumbnail_path = path + ".thumb.jpg"
                    _bucket().upload(thumbnail_path, thumbnail_bytes, file_options={"content-type": "image/jpeg", "upsert": "false"})
                except Exception:
                    thumbnail_path = ""
                    logging.getLogger(__name__).exception("GALLERY_THUMBNAIL_UPLOAD_FAILURE path=%s", path)
            return index, f.name, (path, thumbnail_path, mime), None
        except Exception:
            logging.getLogger(__name__).exception("GALLERY_UPLOAD_FAILURE group=%s file=%s", group.pk, f.name)
            return index, f.name, None, "Yüklenemedi. Depolama ayarlarını kontrol edin."

    # Parallelize independent storage transfers, but persist DB records in file order.
    with ThreadPoolExecutor(max_workers=min(3, len(files))) as pool:
        results = sorted(pool.map(process_file, enumerate(files)), key=lambda row: row[0])
    next_order = (GalleryMedia.objects.filter(group=group).order_by("-sort_order").values_list("sort_order", flat=True).first() or 0)
    failures = []
    successes = 0
    for _, name, uploaded, error in results:
        if error:
            failures.append((name, error))
            continue
        path, thumbnail_path, mime = uploaded
        next_order += 1
        GalleryMedia.objects.create(group=group, storage_path=path, thumbnail_path=thumbnail_path, original_name=name[:255], content_type=mime, sort_order=next_order)
        successes += 1
    if failures:
        details = "; ".join(name + ": " + reason for name, reason in failures)
        messages.error(request, f"{group.album.code} kodlu albüme {len(files)} dosyadan {successes} tanesi yüklendi, {len(failures)} dosya eksik. Başarısız dosyalar: {details}")
        logging.getLogger(__name__).warning("GALLERY_PARTIAL_UPLOAD album=%s group=%s success=%s failed=%s details=%s", group.album.code, group.pk, successes, len(failures), details)
    elif successes:
        messages.success(request, f"{group.album.code} kodlu albüme {successes} dosya başarıyla yüklendi.")
    return redirect("/urun-albumu/?album=" + str(group.album_id) + "&group=" + str(group.pk))

@login_required
def media_view(request, media_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    media = get_object_or_404(GalleryMedia, pk=media_id)
    try:
        thumbnail = request.GET.get("thumb") == "1" and bool(media.thumbnail_path)
        cache_key = "gallery_signed_media_v2_" + str(media.pk) + ("_thumb" if thumbnail else "")
        url = cache.get(cache_key)
        if not url:
            signed = _bucket().create_signed_url(media.thumbnail_path if thumbnail else media.storage_path, 3600)
            url = signed.get("signedURL") or signed.get("signedUrl") or signed.get("signed_url")
            if not url:
                raise ValueError("No signed URL")
            cache.set(cache_key, url, 3300)
        response = redirect(url)
        response["Cache-Control"] = "private, max-age=300"
        return response
    except Exception:
        logging.getLogger(__name__).exception("Gallery media redirect failed media=%s", media.pk)
        raise Http404("Medya açılamadı.")

@login_required
@require_POST
def cover_media(request, media_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    media = get_object_or_404(GalleryMedia, pk=media_id)
    GalleryMedia.objects.filter(group__album_id=media.group.album_id).update(is_cover=False)
    media.is_cover = True
    media.save(update_fields=["is_cover"])
    return redirect("/urun-albumu/?album=" + str(media.group.album_id) + "&group=" + str(media.group_id))

@login_required
@require_POST
def gallery_new_product(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    code = (request.POST.get("kod") or "").strip().upper()
    kind = (request.POST.get("urun_tipi") or "").strip()
    if not code or len(code) > 100 or kind not in dict(URUN_TIPI_CHOICES):
        messages.error(request, "Ürün kodunu ve geçerli ürün tipini girin.")
        return redirect("product_gallery")
    from django.db import transaction
    with transaction.atomic():
        product = UrunKod.objects.filter(kod__iexact=code).first()
        if product:
            if product.aktif:
                messages.error(request, "Bu ürün zaten kayıtlı.")
            else:
                product.aktif = True
                product.urun_tipi = kind
                product.save(update_fields=["aktif", "urun_tipi"])
                messages.success(request, "Ürün yeniden aktifleştirildi.")
        else:
            product = UrunKod.objects.create(kod=code, urun_tipi=kind)
            messages.success(request, "Ürün eklendi.")
        album, _ = GalleryAlbum.objects.get_or_create(code=product.kod)
    return redirect("/urun-albumu/?album=" + str(album.pk))

@login_required
@require_POST
def reorder_media(request, group_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    group = get_object_or_404(GalleryGroup, pk=group_id)
    try:
        ids = json.loads(request.body.decode("utf-8")).get("ids")
        if not isinstance(ids, list) or any(type(pk) is not int for pk in ids) or len(set(ids)) != len(ids):
            return JsonResponse({"error": "Geçersiz sıralama."}, status=400)
        existing = set(GalleryMedia.objects.filter(group=group).values_list("pk", flat=True))
        if set(ids) != existing or len(ids) != len(existing):
            return JsonResponse({"error": "Fotoğraf listesi değişti. Sayfayı yenileyin."}, status=409)
        with transaction.atomic():
            for order, pk in enumerate(ids, 1):
                GalleryMedia.objects.filter(pk=pk, group=group).update(sort_order=order)
        return JsonResponse({"ok": True})
    except (ValueError, TypeError, UnicodeDecodeError):
        return JsonResponse({"error": "Geçersiz istek."}, status=400)

@login_required
@require_POST
def delete_media(request, media_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    media = get_object_or_404(GalleryMedia, pk=media_id)
    album_id, group_id = media.group.album_id, media.group_id
    try:
        _bucket().remove([media.storage_path] + ([media.thumbnail_path] if media.thumbnail_path else []))
    except Exception:
        logging.getLogger(__name__).exception("Gallery deletion failed media=%s", media_id)
        messages.error(request, "Fotoğraf silinemedi.")
        return redirect("/urun-albumu/?album=" + str(album_id) + "&group=" + str(group_id))
    media.delete()
    messages.success(request, "Fotoğraf silindi.")
    return redirect("/urun-albumu/?album=" + str(album_id) + "&group=" + str(group_id))
