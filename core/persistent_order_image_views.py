from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from . import views as core_views
from .models import Order, OrderImage
from .multi_order_views import _upload_order_image


@login_required
def order_edit_persistent(request, pk):
    """Run the existing edit flow, then move any uploaded main image to Supabase."""
    uploaded = request.FILES.get("resim") if request.method == "POST" else None

    response = core_views.order_edit(request, pk)

    # Only persist the image when the original edit completed successfully.
    if uploaded is not None and getattr(response, "status_code", 200) in (301, 302):
        order = get_object_or_404(Order, pk=pk)
        try:
            uploaded.seek(0)
            public_url = _upload_order_image(uploaded, order.siparis_numarasi)
            OrderImage.objects.create(order=order, image_url=public_url)

            # The old ImageField points at Render's ephemeral filesystem.
            # Clear it so the detail page does not render a broken local URL.
            if order.resim:
                order.resim = None
                order.save(update_fields=["resim"])

            messages.success(request, "Sipariş görseli kalıcı olarak yüklendi ✅")
        except Exception as exc:
            messages.error(request, f"Sipariş görseli kalıcı depoya yüklenemedi: {exc}")

    return response


@login_required
def order_detail_persistent(request, pk):
    """Hide stale Render-local image references; persistent images live in OrderImage."""
    order = Order.objects.filter(pk=pk).first()
    if order and order.resim:
        order.resim = None
        order.save(update_fields=["resim"])
    return core_views.order_detail(request, pk)
