import uuid
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from supabase import create_client

from .models import Order, OrderVideo
from .persistent_order_image_views import _delete_supabase_object
from app_settings.access import order_scope_allows


def _can_edit(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


def save_order_video(order, uploaded):
    """Validate and save an order video after its order is persisted."""
    if not uploaded:
        return
    ext = Path(uploaded.name).suffix.lower()
    if ext not in (".mp4", ".mov") or uploaded.size > 100 * 1024 * 1024 or uploaded.size < 12:
        raise ValueError("MP4/MOV ve en fazla 100 MB video seçin.")
    uploaded.seek(0)
    if uploaded.read(16)[4:8] != b"ftyp":
        raise ValueError("Geçerli bir MP4 veya MOV dosyası seçin.")
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("Video depolama ayarları eksik.")
    safe_order = "".join(ch for ch in order.siparis_numarasi if ch.isalnum() or ch in "-_") or "siparis"
    key = f"order-videos/{safe_order}/{uuid.uuid4().hex}{ext}"
    uploaded.seek(0)
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    bucket = client.storage.from_(settings.SUPABASE_BUCKET_NAME)
    bucket.upload(key, uploaded.read(), file_options={"content-type": "video/quicktime" if ext == ".mov" else "video/mp4", "upsert": "false"})
    url = bucket.get_public_url(key)
    try:
        OrderVideo.objects.create(order=order, video_url=url, original_name=Path(uploaded.name).name[:255])
    except Exception:
        bucket.remove([key])
        raise


@login_required
@require_POST
def order_video_upload(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if not _can_edit(request.user) or not order_scope_allows(request.user, order):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")
    uploaded = request.FILES.get("video")
    if not uploaded:
        messages.error(request, "Video dosyası seçin.")
        return redirect("order_detail", pk=pk)
    try:
        save_order_video(order, uploaded)
    except ValueError as exc:
        messages.error(request, str(exc))
    except Exception:
        messages.error(request, "Video yüklenemedi. Supabase dosya boyutu sınırını kontrol edin.")
    else:
        messages.success(request, "Video siparişe eklendi.")
    return redirect("order_detail", pk=pk)


@login_required
@require_POST
def order_video_delete(request, pk, video_id):
    order = get_object_or_404(Order, pk=pk)
    if not _can_edit(request.user) or not order_scope_allows(request.user, order):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")
    video = get_object_or_404(OrderVideo, pk=video_id, order_id=pk)
    try:
        _delete_supabase_object(video.video_url)
    except Exception:
        messages.error(request, "Video depolamadan silinemedi, işlem iptal edildi.")
        return redirect("order_detail", pk=pk)
    video.delete()
    messages.success(request, "Video silindi.")
    return redirect("order_detail", pk=pk)
