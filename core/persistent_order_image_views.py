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
    """Persistent images with direct, independent viewer controls."""
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

        inline_open = (
            "onclick=\"var v=document.getElementById('image-viewer');"
            "var i=document.getElementById('image-viewer-img');"
            "if(v&&i){i.src=this.getAttribute('data-full-image')||this.src;"
            "v.classList.add('open');v.setAttribute('aria-hidden','false');"
            "document.body.style.overflow='hidden';}return false;\" "
            "role=\"button\" tabindex=\"0\" style=\"pointer-events:auto;touch-action:manipulation;cursor:zoom-in;\" "
        )
        html = html.replace(
            'class="img-thumbnail preview-img"',
            f'class="img-thumbnail preview-img" {inline_open}'
        )

        html = html.replace(
            '<div id="image-viewer" class="image-viewer no-print" aria-hidden="true">',
            '<div id="image-viewer" class="image-viewer no-print" aria-hidden="true" '
            'onclick="if(event.target===this){this.classList.remove(\'open\');this.setAttribute(\'aria-hidden\',\'true\');'
            'var i=document.getElementById(\'image-viewer-img\');if(i)i.src=\'\';document.body.style.overflow=\'\';}">'
        )

        html = html.replace(
            '<button type="button" id="image-close-btn" class="image-viewer-btn">✕</button>',
            '<button type="button" id="image-close-btn" class="image-viewer-btn" '
            'onclick="event.preventDefault();event.stopPropagation();var v=document.getElementById(\'image-viewer\');'
            'var i=document.getElementById(\'image-viewer-img\');if(v){v.classList.remove(\'open\');v.setAttribute(\'aria-hidden\',\'true\');}'
            'if(i)i.src=\'\';document.body.style.overflow=\'\';return false;">✕</button>'
        )

        html = html.replace(
            '<button type="button" id="image-print-btn" class="image-viewer-btn">🖨️ Yazdır</button>',
            '<button type="button" id="image-print-btn" class="image-viewer-btn" '
            'onclick="return moliPrintViewerImage(event);">🖨️ Yazdır</button>'
        )

        utility_script = """
<style id="moli-print-image-style">
@media print {
  body.moli-print-image-mode * { visibility: hidden !important; }
  body.moli-print-image-mode #moli-print-image-root,
  body.moli-print-image-mode #moli-print-image-root * { visibility: visible !important; }
  body.moli-print-image-mode #moli-print-image-root {
    position: fixed !important;
    inset: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: #fff !important;
    z-index: 2147483647 !important;
  }
  body.moli-print-image-mode #moli-print-image-root img {
    display: block !important;
    max-width: 100% !important;
    max-height: 100vh !important;
    object-fit: contain !important;
  }
  @page { margin: 10mm; }
}
</style>
<script>
function moliPrintViewerImage(e) {
  if (e) {
    e.preventDefault();
    e.stopPropagation();
  }
  var img = document.getElementById('image-viewer-img');
  if (!img || !img.src) return false;

  var oldRoot = document.getElementById('moli-print-image-root');
  if (oldRoot) oldRoot.remove();

  var root = document.createElement('div');
  root.id = 'moli-print-image-root';
  var printImg = document.createElement('img');
  printImg.src = img.src;
  root.appendChild(printImg);
  document.body.appendChild(root);
  document.body.classList.add('moli-print-image-mode');

  var cleanup = function() {
    document.body.classList.remove('moli-print-image-mode');
    var r = document.getElementById('moli-print-image-root');
    if (r) r.remove();
    window.removeEventListener('afterprint', cleanup);
  };

  window.addEventListener('afterprint', cleanup);
  window.print();
  setTimeout(function() {
    if (document.body.classList.contains('moli-print-image-mode')) cleanup();
  }, 1500);
  return false;
}
</script>
"""
        html = html.replace("</body>", utility_script + "</body>") if "</body>" in html else html + utility_script

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
    if (!src) return false;
    if (!confirm('Bu fotoğraf silinsin mi?')) return false;
    window.location.href = '{delete_base}' + encodeURIComponent(src);
    return false;
  }};
}})();
</script>
"""
            html = html.replace("</body>", script + "</body>") if "</body>" in html else html + script

        response.content = html.encode(response.charset or "utf-8")
        if response.has_header("Content-Length"):
            del response["Content-Length"]

    return response
