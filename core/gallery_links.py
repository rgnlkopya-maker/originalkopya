"""Product album tabs with per-customer photo, Google Photos URL, notes. No Supabase access."""
import base64
import binascii
import hashlib
from io import BytesIO
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from django.db.models import BooleanField, Case, IntegerField, Value, When
from django.http import Http404, HttpResponse, HttpResponseForbidden, HttpResponseNotModified
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from PIL import Image, ImageOps
from core.models import GalleryAlbum, GalleryGroup, GalleryProductionNote

STANDARD_NAMES = ("Standart Model", "Standart")


def _allowed(user):
    return bool(user.is_authenticated and user.is_active)


def _identity_key(value):
    """Normalize Turkish spelling and spacing for restricted individual accounts."""
    import unicodedata

    turkish = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "Ş": "s",
                             "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u",
                             "ö": "o", "Ö": "o", "ç": "c", "Ç": "c"})
    normalized = unicodedata.normalize("NFKD", (value or "").translate(turkish).casefold())
    return "".join(character for character in normalized if character.isalnum())


def _can_edit_album(user):
    """Patron/mudur may edit except the two explicitly excluded accounts."""
    if not _allowed(user):
        return False
    full_name = _identity_key(f"{user.first_name} {user.last_name}")
    username = _identity_key(user.username)
    # Match real names and commonly used username-only accounts; exclusion wins
    # even when an excluded user has patron, mudur or superuser privileges.
    restricted_people = {"eminekanyis", "osmankanyis"}
    restricted_logins = {"eminekanyis", "osmankanyis", "emine", "osman"}
    if full_name in restricted_people or username in restricted_logins:
        return False
    return user.groups.filter(name__in=("patron", "mudur")).exists()


def _valid_google_photos_url(value):
    try:
        parsed = urlparse(value)
        return (parsed.scheme == "https"
                and parsed.hostname in {"photos.google.com", "photos.app.goo.gl"}
                and bool(parsed.path and parsed.path != "/")
                and not parsed.username and not parsed.password)
    except ValueError:
        return False


def _standard_group(album):
    group = GalleryGroup.objects.filter(album=album, name__in=STANDARD_NAMES).order_by("pk").first()
    if group:
        return group
    group, _ = GalleryGroup.objects.get_or_create(
        album=album, name="Standart Model",
        defaults={"google_photos_url": album.google_photos_url,
                  "cover_data_url": album.cover_data_url})
    return group


def _process_cover(upload):
    if not 0 < upload.size <= 8 * 1024 * 1024:
        raise ValueError("Kapak en fazla 8 MB olabilir.")
    try:
        with Image.open(upload) as image:
            image.verify()
        upload.seek(0)
        with Image.open(upload) as image:
            if image.format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError("JPG, PNG veya WEBP kullanın.")
            photo = ImageOps.exif_transpose(image)
            photo.thumbnail((360, 480))
            if photo.mode != "RGB":
                photo = photo.convert("RGB")
            output = BytesIO()
            photo.save(output, format="JPEG", quality=72, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
    except (OSError, Image.DecompressionBombError):
        raise ValueError("Fotoğraf okunamadı.") from None


def _cover_response(stored, request):
    if not stored:
        raise Http404("Kapak bulunamadı.")
    try:
        header, payload = stored.split(",", 1)
        media_type = header.removeprefix("data:").removesuffix(";base64")
        if media_type not in ("image/jpeg", "image/png", "image/webp"):
            raise ValueError("unsupported format")
        photo = base64.b64decode(payload, validate=True)
        if not photo:
            raise ValueError("empty photo")
    except (ValueError, binascii.Error):
        raise Http404("Kapak okunamadı.") from None
    etag = '"' + hashlib.sha256(photo).hexdigest() + '"'
    response = (HttpResponseNotModified() if request.headers.get("If-None-Match") == etag
                else HttpResponse(photo, content_type=media_type))
    response["ETag"] = etag
    response["Cache-Control"] = "private, no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def gallery_links(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Yetkiniz yok.")
    q = (request.GET.get("q") or "").strip()[:80]
    albums = GalleryAlbum.objects.defer("cover_data_url").annotate(
        has_cover=Case(When(cover_data_url="", then=Value(False)),
                       default=Value(True), output_field=BooleanField()))
    if q:
        albums = albums.filter(code__icontains=q)
    page = Paginator(albums.order_by("code", "pk"), 24).get_page(request.GET.get("page"))
    can_edit = _can_edit_album(request.user)
    selected, groups, active, notes = None, [], None, []
    edit = request.GET.get("edit") == "1"
    identifier = request.GET.get("album", "")
    if identifier.isdigit():
        selected = get_object_or_404(GalleryAlbum, pk=int(identifier))
        if edit and not can_edit:
            return HttpResponseForbidden("Bu albümü düzenleme yetkiniz yok.")
        standard = _standard_group(selected)
        groups = list(GalleryGroup.objects.filter(album=selected).defer("cover_data_url").annotate(
            has_cover=Case(When(cover_data_url="", then=Value(False)),
                           default=Value(True), output_field=BooleanField()),
            rank=Case(When(name__in=STANDARD_NAMES, then=Value(0)),
                      default=Value(1), output_field=IntegerField()),
        ).order_by("rank", "pk"))
        requested = request.GET.get("group", "")
        active = next((g for g in groups if str(g.pk) == requested),
                      next((g for g in groups if g.pk == standard.pk), groups[0]))
        notes = list(GalleryProductionNote.objects.filter(
            group_id=active.pk, deleted_at__isnull=True
        ).select_related("created_by").order_by("created_at", "pk"))
    return render(request, "core/gallery_links.html", {
        "albums": page.object_list, "page_obj": page,
        "selected": selected, "groups": groups, "active_group": active,
        "notes": notes, "edit_mode": edit, "can_edit_album": can_edit, "search_query": q,
    })


@login_required
def gallery_cover_image(request, album_id):
    album = get_object_or_404(GalleryAlbum.objects.only("cover_data_url"), pk=album_id)
    return _cover_response(album.cover_data_url, request)


@login_required
def gallery_group_cover_image(request, group_id):
    group = get_object_or_404(GalleryGroup.objects.only("cover_data_url"), pk=group_id)
    return _cover_response(group.cover_data_url, request)


def _save_changes(request, group):
    url = (request.POST.get("google_photos_url") or "").strip()
    if url and not _valid_google_photos_url(url):
        raise ValueError("Geçerli Google Photos albüm bağlantısı girin.")
    upload = request.FILES.get("cover")
    cover = _process_cover(upload) if upload else None
    with transaction.atomic():
        group.google_photos_url = url
        updates = ["google_photos_url"]
        if cover is not None:
            group.cover_data_url = cover
            updates.append("cover_data_url")
        group.save(update_fields=updates)
        if group.name in STANDARD_NAMES:
            album = group.album
            album.google_photos_url = url
            updates = ["google_photos_url"]
            if cover is not None:
                album.cover_data_url = cover
                updates.append("cover_data_url")
            album.save(update_fields=updates)


@login_required
@require_POST
def gallery_group_save(request, group_id):
    if not _can_edit_album(request.user):
        return HttpResponseForbidden("Bu albümü düzenleme yetkiniz yok.")
    group = get_object_or_404(GalleryGroup.objects.select_related("album"), pk=group_id)
    destination = f"/urun-albumu/?album={group.album_id}&group={group.pk}"
    try:
        _save_changes(request, group)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(destination + "&edit=1")
    messages.success(request, "Kaydedildi.")
    return redirect(destination)


@login_required
@require_POST
def gallery_link_save(request, album_id):
    """Keep the previous standard-album save route working safely."""
    if not _can_edit_album(request.user):
        return HttpResponseForbidden("Bu albümü düzenleme yetkiniz yok.")
    album = get_object_or_404(GalleryAlbum, pk=album_id)
    group = _standard_group(album)
    try:
        _save_changes(request, group)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(f"/urun-albumu/?album={album.pk}&group={group.pk}&edit=1")
    messages.success(request, "Kaydedildi.")
    return redirect(f"/urun-albumu/?album={album.pk}&group={group.pk}")


@login_required
@require_POST
def gallery_customer_add(request, album_id):
    if not _can_edit_album(request.user):
        return HttpResponseForbidden("Müşteri sekmesi ekleme yetkiniz yok.")
    album = get_object_or_404(GalleryAlbum, pk=album_id)
    name = " ".join((request.POST.get("name") or "").split())
    if not name or len(name) > 160 or name.casefold() in ("standart", "standart model"):
        messages.error(request, "Geçerli müşteri adı girin.")
        return redirect(f"/urun-albumu/?album={album.pk}")
    group, created = GalleryGroup.objects.get_or_create(album=album, name=name)
    messages.success(request, "Sekme oluşturuldu." if created else "Bu sekme zaten mevcut.")
    return redirect(f"/urun-albumu/?album={album.pk}&group={group.pk}")

@login_required
@require_POST
def gallery_note_add(request, group_id):
    """All active signed-in users may append; they cannot overwrite previous notes."""
    if not _allowed(request.user):
        return HttpResponseForbidden("Not ekleme yetkiniz yok.")
    group = get_object_or_404(GalleryGroup, pk=group_id)
    destination = f"/urun-albumu/?album={group.album_id}&group={group.pk}"
    body = (request.POST.get("body") or "").strip()
    if not body or len(body) > 5000:
        messages.error(request, "1 ile 5.000 karakter arasında bir üretim notu girin.")
        return redirect(destination)
    GalleryProductionNote.objects.create(group=group, body=body, created_by=request.user)
    messages.success(request, "Üretim notu eklendi.")
    return redirect(destination)


@login_required
@require_POST
def gallery_note_delete(request, note_id):
    """Only managers may soft-delete. Existing note text remains in the database."""
    if not _can_edit_album(request.user):
        return HttpResponseForbidden("Üretim notu silme yetkiniz yok.")
    note = get_object_or_404(
        GalleryProductionNote.objects.select_related("group"),
        pk=note_id, deleted_at__isnull=True
    )
    note.deleted_at = timezone.now()
    note.deleted_by = request.user
    note.save(update_fields=["deleted_at", "deleted_by"])
    messages.success(request, "Üretim notu kaldırıldı.")
    return redirect(f"/urun-albumu/?album={note.group.album_id}&group={note.group_id}")
