"""Simple product album links. No Supabase reads, writes or deletions."""
import base64
import binascii
import hashlib
from io import BytesIO
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import BooleanField, Case, Value, When
from django.http import Http404, HttpResponse, HttpResponseForbidden, HttpResponseNotModified
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from PIL import Image, ImageOps

from core.models import GalleryAlbum, UrunKod, URUN_TIPI_CHOICES


def _allowed(user):
    return user.is_authenticated and user.is_active


def _can_edit_album(user):
    """Only the active 'mudur' group may edit album covers and links."""
    return _allowed(user) and user.groups.filter(name="mudur").exists()


def _valid_google_photos_url(value):
    try:
        parsed = urlparse(value)
        return parsed.scheme == "https" and parsed.hostname in {
            "photos.google.com", "photos.app.goo.gl"
        } and bool(parsed.path and parsed.path != "/") and not parsed.username and not parsed.password
    except ValueError:
        return False


@login_required
def gallery_links(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    query = (request.GET.get("q") or "").strip()[:80]
    # Never include large base64 cover data in the HTML or listing query results.
    albums = GalleryAlbum.objects.defer("cover_data_url").annotate(
        has_cover=Case(
            When(cover_data_url="", then=Value(False)),
            default=Value(True),
            output_field=BooleanField(),
        )
    )
    if query:
        albums = albums.filter(code__icontains=query)
    page = Paginator(albums.order_by("code", "pk"), 24).get_page(request.GET.get("page"))
    can_edit_album = _can_edit_album(request.user)
    selected_id = request.GET.get("album", "")
    if selected_id.isdigit() and not can_edit_album:
        return HttpResponseForbidden("Albüm düzenleme yetkisi yalnızca müdüre aittir.")
    selected = albums.filter(pk=selected_id).first() if selected_id.isdigit() else None
    return render(request, "core/gallery_links.html", {
        "albums": page.object_list, "page_obj": page, "selected": selected,
        "can_edit_album": can_edit_album,
        "search_query": query,
        "products": UrunKod.objects.filter(aktif=True).order_by("kod"),
        "product_types": URUN_TIPI_CHOICES,
    })



@login_required
def gallery_cover_image(request, album_id):
    """Serve one existing cover on demand. No Supabase access or mutations."""
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    stored = get_object_or_404(
        GalleryAlbum.objects.only("id", "cover_data_url"), pk=album_id
    ).cover_data_url
    if not stored:
        raise Http404("Kapak bulunamadı.")
    try:
        data_header, encoded = stored.split(",", 1)
        content_type = data_header.removeprefix("data:").removesuffix(";base64")
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("Unsupported cover format")
        data = base64.b64decode(encoded, validate=True)
        if not data:
            raise ValueError("Empty cover")
    except (ValueError, binascii.Error):
        raise Http404("Kapak okunamadı.")

    etag = '"' + hashlib.sha256(data).hexdigest() + '"'
    if request.headers.get("If-None-Match") == etag:
        response = HttpResponseNotModified()
    else:
        response = HttpResponse(data, content_type=content_type)
    response["ETag"] = etag
    # Revalidate when revisiting so a changed cover appears immediately.
    # The browser can reuse its cached bytes on 304 responses.
    response["Cache-Control"] = "private, no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_POST
def gallery_link_save(request, album_id):
    if not _can_edit_album(request.user):
        return HttpResponseForbidden("Albüm düzenleme yetkisi yalnızca müdüre aittir.")
    album = get_object_or_404(GalleryAlbum, pk=album_id)
    url = (request.POST.get("google_photos_url") or "").strip()
    if url and not _valid_google_photos_url(url):
        messages.error(request, "Geçerli bir Google Photos albüm bağlantısı girin.")
        return redirect(f"/urun-albumu/?album={album.pk}")
    album.google_photos_url = url
    fields = ["google_photos_url"]
    upload = request.FILES.get("cover")
    if upload:
        if upload.size > 8 * 1024 * 1024 or upload.size == 0:
            messages.error(request, "Kapak fotoğrafı en fazla 8 MB olabilir.")
            return redirect(f"/urun-albumu/?album={album.pk}")
        try:
            with Image.open(upload) as source:
                source.verify()
            upload.seek(0)
            with Image.open(upload) as source:
                if source.format not in ("JPEG", "PNG", "WEBP"):
                    raise ValueError("unsupported")
                cover = ImageOps.exif_transpose(source)
                cover.thumbnail((360, 480))
                if cover.mode != "RGB":
                    cover = cover.convert("RGB")
                output = BytesIO()
                cover.save(output, format="JPEG", quality=72, optimize=True)
            album.cover_data_url = "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
            fields.append("cover_data_url")
        except (OSError, ValueError, Image.DecompressionBombError):
            messages.error(request, "Kapak fotoğrafı okunamadı. JPG, PNG veya WEBP kullanın.")
            return redirect(f"/urun-albumu/?album={album.pk}")
    album.save(update_fields=fields)
    messages.success(request, "Albüm bağlantısı ve kapak kaydedildi.")
    return redirect("/urun-albumu/?album=" + str(album.pk))
