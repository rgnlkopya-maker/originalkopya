"""Initial, read-only smart-pattern workspace; no CAD calculations or cutting outputs."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from core.models import Order, UrunKod
from app_settings.access import has_full_access
from django.contrib import messages
from django.views.decorators.http import require_POST
from .smart_pattern_models import SmartPatternMaster


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
    return render(request, "product_cards/smart_pattern_home.html", {
        "products": UrunKod.objects.filter(aktif=True).order_by("kod"),
        "masters": SmartPatternMaster.objects.select_related("product").all(),
    })


@login_required
@require_POST
def smart_pattern_master_save(request):
    if not has_full_access(request.user):
        return HttpResponseForbidden("Bu işlem için yönetici yetkisi gerekli.")
    product_id = request.POST.get("product_id", "").strip()
    model_type = request.POST.get("model_type", "").strip()
    notes = request.POST.get("notes", "").strip()
    if model_type not in dict(SmartPatternMaster.MODEL_TYPES):
        messages.error(request, "Lütfen geçerli bir model türü seçin.")
        return redirect("smart_pattern_home")
    if len(notes) > 2000:
        messages.error(request, "Not alanı en fazla 2000 karakter olabilir.")
        return redirect("smart_pattern_home")
    product = UrunKod.objects.filter(pk=product_id, aktif=True).first() if product_id.isdecimal() else None
    if not product:
        messages.error(request, "Lütfen kayıtlı bir ürün kodu seçin.")
        return redirect("smart_pattern_home")
    master, created = SmartPatternMaster.objects.update_or_create(
        product=product,
        defaults={"model_type": model_type, "notes": notes,
                  **({"created_by": request.user} if not SmartPatternMaster.objects.filter(product=product).exists() else {})},
    )
    messages.success(request, f"{product.kod} ana kalıp kaydı {'oluşturuldu' if created else 'güncellendi'}.")
    return redirect("smart_pattern_home")
