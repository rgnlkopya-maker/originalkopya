"""Initial, read-only smart-pattern workspace; no CAD calculations or cutting outputs."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from core.models import Order
from app_settings.access import has_full_access


@login_required
def smart_pattern_order(request, order_id):
    if not has_full_access(request.user):
        return HttpResponseForbidden("Akıllı Kalıp ekranı için yönetici yetkisi gerekli.")
    order = get_object_or_404(Order.objects.select_related("musteri"), pk=order_id)
    if order.siparis_tipi != "OZEL":
        return HttpResponseForbidden("Akıllı Kalıp yalnızca özel siparişlerde kullanılabilir.")
    return render(request, "product_cards/smart_pattern_order.html", {"order": order})


@login_required
def smart_pattern_home(request):
    if not has_full_access(request.user):
        return HttpResponseForbidden("Akıllı Kalıp ekranı için yönetici yetkisi gerekli.")
    special_orders = (Order.objects.filter(siparis_tipi="OZEL")
                      .select_related("musteri").order_by("-id")[:100])
    return render(request, "product_cards/smart_pattern_home.html",
                  {"special_orders": special_orders})
