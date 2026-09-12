from django.http import Http404
from django.shortcuts import render

from core.models import UrunKod
from .models import ProductCard


TEST_PUBLIC_PRODUCT_CODE = "7167"


def public_product_page(request, code):
    """QR ile açılacak, giriş gerektirmeyen sade ürün sayfası.

    İlk aşamada yalnızca 7167 deneme ürünü açıktır. Butonlar henüz işlem yapmaz;
    yalnızca giriş durumuna göre doğru senaryoyu gösterir.
    """
    normalized_code = (code or "").strip().upper()
    if normalized_code != TEST_PUBLIC_PRODUCT_CODE:
        raise Http404("Ürün bulunamadı.")

    product = UrunKod.objects.filter(kod__iexact=normalized_code, aktif=True).first()
    if not product:
        raise Http404("Ürün bulunamadı.")

    card = ProductCard.objects.filter(urun=product).first()
    is_manager = bool(
        request.user.is_authenticated
        and request.user.groups.filter(name__in=["patron", "mudur"]).exists()
    )

    return render(request, "product_cards/public_product.html", {
        "product": product,
        "card": card,
        "is_manager": is_manager,
        "is_authenticated": request.user.is_authenticated,
    })
