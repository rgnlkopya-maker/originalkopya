from urllib.parse import urlparse

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
    """Delete the exact persistent image selected in the image viewer."""
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
    """Use persistent images while preserving the original image viewer behavior."""
    order = Order.objects.filter(pk=pk).first()
    if order and order.resim:
        order.resim = None
        order.save(update_fields=["resim"])

    response = core_views.order_detail(request, pk)

    # Do NOT change the existing image click/zoom/close handlers.
    # Only add a separate delete button for managers.
    if (
        getattr(response, "status_code", 200) == 200
        and request.user.groups.filter(name__in=["patron", "mudur"]).exists()
        and response.get("Content-Type", "").startswith("text/html")
    ):
        delete_base = f"/order/{pk}/delete-image-by-url/?url="
        script = f"""
<script>
document.addEventListener('DOMContentLoaded', function() {{
  const actions = document.querySelector('.image-viewer-actions');
  const viewerImg = document.getElementById('image-viewer-img');
  const closeBtn = document.getElementById('image-close-btn');
  if (!actions || !viewerImg || !closeBtn) return;

  // X remains the original close button. Add delete as a completely separate control.
  if (!document.getElementById('image-delete-btn')) {{
    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.id = 'image-delete-btn';
    deleteBtn.className = 'image-viewer-btn';
    deleteBtn.textContent = '🗑️ Sil';
    deleteBtn.title = 'Bu görseli sil';
    actions.insertBefore(deleteBtn, closeBtn);

    deleteBtn.addEventListener('click', function(e) {{
      e.preventDefault();
      e.stopPropagation();
      const src = viewerImg.src;
      if (!src) return;
      if (!confirm('Bu fotoğraf silinsin mi?')) return;
      window.location.href = '{delete_base}' + encodeURIComponent(src);
    }});
  }}
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
