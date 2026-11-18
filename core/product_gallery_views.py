import os
import logging
from uuid import uuid4
from django.db import IntegrityError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from app_settings.access import has_full_access
from core.models import GalleryAlbum, GalleryGroup, GalleryMedia, UrunKod, URUN_TIPI_CHOICES
from supabase import create_client

def _allowed(user):
    return has_full_access(user)

def _bucket():
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Görsel depolama ayarları eksik.")
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    name = os.getenv("SUPABASE_GALLERY_BUCKET", "moli-product-gallery")
    try:
        client.storage.get_bucket(name)
    except Exception as exc:
        if not any(x in str(exc).lower() for x in ("404", "not found", "does not exist")):
            raise
        client.storage.create_bucket(name, options={"public": False})
    return client.storage.from_(name)

@login_required
def product_gallery(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Ürün Albümü erişim yetkiniz yok.")
    # Backfill albums for products created before automatic gallery creation was enabled.
    existing_codes = set(GalleryAlbum.objects.values_list("code", flat=True))
    missing = [GalleryAlbum(code=code) for code in UrunKod.objects.filter(aktif=True).values_list("kod", flat=True) if code not in existing_codes]
    if missing:
        GalleryAlbum.objects.bulk_create(missing, ignore_conflicts=True, batch_size=500)
    albums = list(GalleryAlbum.objects.prefetch_related("groups__media"))
    albums.sort(key=lambda a: (0, int(a.code)) if a.code.isdigit() else (1, a.code.casefold()))
    selected = None
    if request.GET.get("album"):
        selected = next((a for a in albums if str(a.pk) == request.GET["album"]), None)
    if selected:
        GalleryGroup.objects.get_or_create(album=selected, name="Standart Model")
        selected = GalleryAlbum.objects.prefetch_related("groups__media").get(pk=selected.pk)
    for album in albums:
        album.cover = next((m for g in album.groups.all() for m in g.media.all() if m.is_cover), None)
        if album.cover is None:
            album.cover = next((m for g in album.groups.all() for m in g.media.all()), None)
    return render(request, "core/product_gallery.html", {"albums": albums, "selected": selected, "products": UrunKod.objects.filter(aktif=True).order_by("kod"), "product_types": URUN_TIPI_CHOICES, "urun_tipi_secenekleri": URUN_TIPI_CHOICES, "aktif_urun_kodlari": UrunKod.objects.filter(aktif=True).order_by("kod")})

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
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    album = get_object_or_404(GalleryAlbum, pk=album_id)
    name = " ".join(request.POST.get("name", "").split())
    if not name or len(name) > 160:
        messages.error(request, "Lütfen geçerli bir müşteri adı girin.")
        return redirect("/urun-albumu/?album=" + str(album.pk))
    try:
        group, created = GalleryGroup.objects.get_or_create(album=album, name=name)
    except IntegrityError:
        group = GalleryGroup.objects.filter(album=album, name=name).first()
        if group is None:
            logging.getLogger(__name__).exception("Gallery group creation integrity error album=%s", album.pk)
            messages.error(request, "Grup oluşturulamadı. Lütfen tekrar deneyin.")
            return redirect("/urun-albumu/?album=" + str(album.pk))
        created = False
    except Exception:
        logging.getLogger(__name__).exception("Gallery group creation failed album=%s", album.pk)
        messages.error(request, "Grup oluşturulurken hata oluştu. Lütfen tekrar deneyin.")
        return redirect("/urun-albumu/?album=" + str(album.pk))
    messages.success(request, "Müşteri sekmesi oluşturuldu." if created else "Bu müşteri sekmesi zaten mevcut.")
    return redirect("/urun-albumu/?album=" + str(album.pk) + "&group=" + str(group.pk))

@login_required
@require_POST
def upload_media(request, group_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    group = get_object_or_404(GalleryGroup, pk=group_id)
    files = request.FILES.getlist("media")
    if not files or len(files) > 15:
        messages.error(request, "Bir seferde 1-15 fotoğraf veya video seçin.")
        return redirect("/urun-albumu/?album=" + str(group.album_id))
    for f in files:
        if f.size > 100 * 1024 * 1024 or f.size == 0:
            messages.error(request, f.name + ": Dosya boyutu geçersiz (en fazla 100 MB).")
            continue
        signature = f.read(16)
        f.seek(0)
        from PIL import Image, UnidentifiedImageError
        mime = None
        try:
            with Image.open(f) as img:
                img.verify()
            mime = "image/jpeg" if signature.startswith(b"\\xff\\xd8\\xff") else ("image/png" if signature.startswith(b"\\x89PNG") else ("image/webp" if signature.startswith(b"RIFF") and signature[8:12] == b"WEBP" else None))
        except (UnidentifiedImageError, OSError, ValueError):
            pass
        if mime is None and len(signature) >= 12 and signature[4:8] == b"ftyp" and signature[8:12] in (b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"qt  "):
            mime = "video/mp4"
        if not mime:
            messages.error(request, f.name + ": Desteklenen türler JPG, PNG, WEBP ve MP4.")
            continue
        ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "video/mp4": ".mp4"}[mime]
        path = f"gallery/{group.album_id}/{uuid4().hex}{ext}"
        try:
            _bucket().upload(path, f.read(), file_options={"content-type": mime, "upsert": "false"})
            GalleryMedia.objects.create(group=group, storage_path=path, original_name=f.name[:255], content_type=mime)
            messages.success(request, f.name + " yüklendi.")
        except Exception:
            messages.error(request, f.name + ": Yüklenemedi. Depolama ayarlarını kontrol edin.")
    return redirect("/urun-albumu/?album=" + str(group.album_id))

@login_required
def media_view(request, media_id):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    media = get_object_or_404(GalleryMedia, pk=media_id)
    try:
        signed = _bucket().create_signed_url(media.storage_path, 120)
        url = signed.get("signedURL") or signed.get("signedUrl") or signed.get("signed_url")
        if not url:
            raise ValueError("No signed URL")
        response = redirect(url)
        response["Cache-Control"] = "private, no-store"
        return response
    except Exception:
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
    return redirect("/urun-albumu/?album=" + str(media.group.album_id))

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
