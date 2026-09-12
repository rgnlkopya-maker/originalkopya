from decimal import Decimal

from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.models import Beden, Renk, UrunKod
from .models import PriceListSettings, ProductCard, ShowroomDraftItem
from .price_list_views import _price_rows
from .showroom_views import _active_draft, _create_draft


TEST_PUBLIC_PRODUCT_CODE = "7167"


def _manager_user(user):
    return bool(
        user.is_authenticated
        and user.groups.filter(name__in=["patron", "mudur"]).exists()
    )


def _test_product(code):
    normalized_code = (code or "").strip().upper()
    if normalized_code != TEST_PUBLIC_PRODUCT_CODE:
        raise Http404("Ürün bulunamadı.")
    product = UrunKod.objects.filter(kod__iexact=normalized_code, aktif=True).first()
    if not product:
        raise Http404("Ürün bulunamadı.")
    return product


def public_product_page(request, code):
    """QR ile açılan, giriş gerektirmeyen sade ürün sayfası."""
    product = _test_product(code)
    card = ProductCard.objects.filter(urun=product).first()
    return render(request, "product_cards/public_product.html", {
        "product": product,
        "card": card,
        "is_manager": _manager_user(request.user),
        "is_authenticated": request.user.is_authenticated,
        "added_to_sheet": request.GET.get("eklendi") == "1",
        "added_with_details": request.GET.get("detayli") == "1",
        "renkler": Renk.objects.filter(aktif=True).order_by("ad"),
        "bedenler": Beden.objects.filter(aktif=True).order_by("ad"),
    })


@require_POST
def public_product_add_to_sheet(request, code):
    """QR ürününü müdür/patronun mevcut açık Föyüne ekler.

    İki kullanım desteklenir:
    - quick: renk/beden seçmeden 1 adet hızlı ekleme
    - detailed: seçilen renk, beden ve adet ile ekleme
    """
    if not _manager_user(request.user):
        return HttpResponseForbidden("Bu işlem için müdür veya patron girişi gerekir.")

    product = _test_product(code)
    card = ProductCard.objects.filter(urun=product, price_list_active=True).first()
    if not card:
        raise Http404("Bu ürün aktif fiyat listesinde bulunamadı.")

    settings = PriceListSettings.get_solo()
    price_row = next((row for row in _price_rows(settings, active=True) if row["id"] == card.id), None)
    if not price_row:
        raise Http404("Ürün fiyatı bulunamadı.")

    mode = (request.POST.get("mode") or "quick").strip().lower()
    color = ""
    size = ""
    quantity = 1

    if mode == "detailed":
        color = (request.POST.get("renk") or "").strip()
        size = (request.POST.get("beden") or "").strip()
        try:
            quantity = max(1, int(request.POST.get("adet") or 1))
        except (TypeError, ValueError):
            quantity = 1

        if color and not Renk.objects.filter(ad__iexact=color, aktif=True).exists():
            color = ""
        if size and not Beden.objects.filter(ad__iexact=size, aktif=True).exists():
            size = ""

    draft = _active_draft(request.user) or _create_draft(request.user)
    ShowroomDraftItem.objects.create(
        draft=draft,
        product_card=card,
        color=color,
        size=size,
        description="",
        quantity=quantity,
        unit_price=price_row.get("cash") or Decimal("0"),
    )
    suffix = "&detayli=1" if mode == "detailed" else ""
    return redirect(f"/urun-kartlari/qr/urun/{product.kod}/?eklendi=1{suffix}")
