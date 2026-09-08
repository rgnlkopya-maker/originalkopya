from urllib.parse import quote, urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from supabase import create_client

from . import views as core_views
from .models import Order, OrderImage
from .multi_order_views import _upload_order_image


@login_required
def order_edit_persistent(request, pk):
    """Run the existing edit flow, then move any uploaded main image to Supabase."""
    uploaded = request.FILES.get("resim") if request.method == "POST" else None

    response = core_views.order_edit(request, pk)

    if uploaded is not None and getattr(response, "status_code", 200) in (301, 302):
        order = get_object_or_404(Order, pk=pk)
        try:
            uploaded.seek(0)
            public_url = _upload_order_image(uploaded, order.siparis_numarasi)
            OrderImage.objects.create(order=order, image_url=public_url)

            if order.resim:
                order.resim = None
                order.save(update_fields=["resim"])

            messages.success(request, "Sipariş görseli kalıcı olarak yüklendi ✅")
        except Exception as exc:
            messages.error(request, f"Sipariş görseli kalıcı depoya yüklenemedi: {exc}")

    return response


def _delete_supabase_object(public_url):
    """Best-effort removal of the object behind a Supabase public URL."""
    if not public_url or not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        return

    bucket_name = settings.SUPABASE_BUCKET_NAME
    marker = f"/object/public/{bucket_name}/"
    path = urlparse(public_url).path
    if marker not in path:
        return

    object_path = path.split(marker, 1)[1]
    if not object_path:
        return

    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    client.storage.from_(bucket_name).remove([object_path])


@login_required
def delete_order_image_by_url(request, pk):
    """Delete the exact persistent image currently open in the image viewer."""
    if not request.user.groups.filter(name__in=["patron", "mudur"]).exists():
        return HttpResponseForbidden("Bu işlemi yapma yetkiniz yok.")

    image_url = (request.GET.get("url") or "").strip()
    image = get_object_or_404(OrderImage, order_id=pk, image_url=image_url)

    try:
        _delete_supabase_object(image.image_url)
    except Exception as exc:
        print("Supabase görsel silme hatası:", exc)

    image.delete()
    messages.success(request, "Görsel başarıyla silindi ✅")
    return redirect("order_detail", pk=pk)


@login_required
def order_detail_persistent(request, pk):
    """Hide stale local images and make the viewer X delete the selected persistent image."""
    order = Order.objects.filter(pk=pk).first()
    if order and order.resim:
        order.resim = None
        order.save(update_fields=["resim"])

    response = core_views.order_detail(request, pk)

    # The existing viewer uses X as a close button. On the order detail page,
    # managers expect that X to delete the open photo. Capture the click before
    # the old handler runs; clicking the dark backdrop still only closes viewer.
    if (
        getattr(response, "status_code", 200) == 200
        and request.user.groups.filter(name__in=["patron", "mudur"]).exists()
        and response.get("Content-Type", "").startswith("text/html")
    ):
        delete_base = f"/order/{pk}/delete-image-by-url/?url="
        script = f"""
<script>
document.addEventListener('DOMContentLoaded', function() {{
  const closeBtn = document.getElementById('image-close-btn');
  const viewerImg = document.getElementById('image-viewer-img');
  if (!closeBtn || !viewerImg) return;

  closeBtn.title = 'Bu görseli sil';
  closeBtn.setAttribute('aria-label', 'Bu görseli sil');

  closeBtn.addEventListener('click', function(e) {{
    const src = viewerImg.src;
    if (!src) return;
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    if (!confirm('Bu fotoğraf silinsin mi?')) return;
    window.location.href = '{delete_base}' + encodeURIComponent(src);
  }}, true);
}});
</script>
"""
        html = response.content.decode(response.charset or "utf-8")
        if "</body>" in html:
            html = html.replace("</body>", script + "</body>")
        else:
            html += script
        response.content = html.encode(response.charset or "utf-8")
        if response.has_header("Content-Length"):
            del response["Content-Length"]

    return response
