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
    """Keep persistent images and make thumbnail click independent of listener timing."""
    order = Order.objects.filter(pk=pk).first()
    if order and order.resim:
        order.resim = None
        order.save(update_fields=["resim"])

    response = core_views.order_detail(request, pk)

    if (
        getattr(response, "status_code", 200) == 200
        and response.get("Content-Type", "").startswith("text/html")
    ):
        html = response.content.decode(response.charset or "utf-8")

        # Direct inline binding on every rendered thumbnail. This does not depend
        # on DOMContentLoaded, delegated listeners, Safari timing, or later DOM changes.
        inline_open = (
            "onclick=\"var v=document.getElementById('image-viewer');"
            "var i=document.getElementById('image-viewer-img');"
            "if(v&&i){i.src=this.getAttribute('data-full-image')||this.src;"
            "v.classList.add('open');v.setAttribute('aria-hidden','false');"
            "document.body.style.overflow='hidden';}return false;\" "
            "role=\"button\" tabindex=\"0\" style=\"pointer-events:auto;touch-action:manipulation;cursor:zoom-in;\" "
        )
        html = html.replace('class="img-thumbnail preview-img"', f'class="img-thumbnail preview-img" {inline_open}')

        # Remove the previously injected delegated-click script if it is present
        # by not adding another one. Keep only a small independent delete button.
        if request.user.groups.filter(name__in=["patron", "mudur"]).exists():
            delete_base = f"/order/{pk}/delete-image-by-url/?url="
            script = f"""
<script>
(function() {{
  const actions = document.querySelector('.image-viewer-actions');
  const closeBtn = document.getElementById('image-close-btn');
  const viewerImg = document.getElementById('image-viewer-img');
  if (!actions || !closeBtn || !viewerImg || document.getElementById('image-delete-btn')) return;

  const deleteBtn = document.createElement('button');
  deleteBtn.type = 'button';
  deleteBtn.id = 'image-delete-btn';
  deleteBtn.className = 'image-viewer-btn';
  deleteBtn.textContent = '🗑️ Sil';
  deleteBtn.title = 'Bu görseli sil';
  actions.insertBefore(deleteBtn, closeBtn);

  deleteBtn.onclick = function(e) {{
    e.preventDefault();
    e.stopPropagation();
    const src = viewerImg.src || '';
    if (!src) return;
    if (!confirm('Bu fotoğraf silinsin mi?')) return;
    window.location.href = '{delete_base}' + encodeURIComponent(src);
  }};
}})();
</script>
"""
            if "</body>" in html:
                html = html.replace("</body>", script + "</body>")
            else:
                html += script

        response.content = html.encode(response.charset or "utf-8")
        if response.has_header("Content-Length"):
            del response["Content-Length"]

    return response
