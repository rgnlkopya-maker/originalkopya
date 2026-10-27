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
from .services.order_access import order_scope_allows


def _can_edit(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


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
    ext = Path(uploaded.name).suffix.lower()
    if ext not in (".mp4", ".mov") or uploaded.size > 100 * 1024 * 1024 or uploaded.size < 12:
        messages.error(request, "Yalnızca 100 MB altındaki MP4 veya MOV videolar kabul edilir.")
        return redirect("order_detail", pk=pk)
    uploaded.seek(0)
    header = uploaded.read(16)
    if len(header) < 12 or header[4:8] != b"ftyp":
        messages.error(request, "Dosya geçerli bir MP4/MOV videosu değil.")
        return redirect("order_detail", pk=pk)
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        messages.error(request, "Video depolama bağlantısı yapılandırılmamış.")
        return redirect("order_detail", pk=pk)
    safe_order = "".join(ch for ch in order.siparis_numarasi if ch.isalnum() or ch in "-_") or "siparis"
    key = f"order-videos/{safe_order}/{uuid.uuid4().hex}{ext}"
    content_type = "video/quicktime" if ext == ".mov" else "video/mp4"
    try:
        uploaded.seek(0)
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        bucket = client.storage.from_(settings.SUPABASE_BUCKET_NAME)
        bucket.upload(key, uploaded.read(), file_options={"content-type": content_type, "upsert": "false"})
        url = bucket.get_public_url(key)
        try:
            OrderVideo.objects.create(order=order, video_url=url, original_name=Path(uploaded.name).name[:255])
        except Exception:
            bucket.remove([key])
            raise
    except Exception:
        messages.error(request, "Video yüklenemedi. Supabase boyut ve dosya ayarlarını kontrol edin.")
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
