from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from app_settings.access import has_access

@login_required
def product_gallery(request):
    if not (request.user.is_superuser or request.user.is_staff or has_access(request.user, "can_manage_products")):
        return HttpResponseForbidden("Ürün Albümü erişim yetkiniz yok.")
    return render(request, "core/product_gallery.html")
