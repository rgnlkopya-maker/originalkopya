from decimal import Decimal

from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.models import Beden, Renk, UrunKod
from .models import PriceListSettings, ProductCard, ShowroomDraftItem
from .price_list_views import _price_rows
from .showroom_views import _active_draft, _create_draft


TEST_PUBLIC_PRODUCT_CODE = "7167"
GUEST_CART_SESSION_KEY = "moli_guest_showroom_cart_v1"


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


def _guest_cart(request):
    cart = request.session.get(GUEST_CART_SESSION_KEY, {})
    return cart if isinstance(cart, dict) else {}


def _guest_cart_count(request):
    cart = _guest_cart(request)
    total = 0
    for qty in cart.values():
        try:
            total += max(0, int(qty))
        except (TypeError, ValueError):
            pass
    return total


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
        "added_to_cart": request.GET.get("sepete") == "1",
        "cart_count": _guest_cart_count(request),
        "renkler": Renk.objects.filter(aktif=True).order_by("ad"),
        "bedenler": Beden.objects.filter(aktif=True).order_by("ad"),
    })


@require_POST
def public_product_add_to_sheet(request, code):
    """QR ürününü müdür/patronun mevcut açık Föyüne ekler."""
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


@require_POST
def public_product_add_to_cart(request, code):
    """Girişsiz ziyaretçinin QR ürününü kendi tarayıcı oturumundaki sepete ekler."""
    if _manager_user(request.user):
        return HttpResponseForbidden("Müdür/patron hesabında ürünleri Sipariş Föyüne ekleyin.")
    product = _test_product(code)
    if not ProductCard.objects.filter(urun=product, price_list_active=True).exists():
        raise Http404("Bu ürün aktif değil.")

    cart = _guest_cart(request)
    current = cart.get(product.kod, 0)
    try:
        current = int(current)
    except (TypeError, ValueError):
        current = 0
    cart[product.kod] = max(0, current) + 1
    request.session[GUEST_CART_SESSION_KEY] = cart
    request.session.modified = True
    return redirect(f"/urun-kartlari/qr/urun/{product.kod}/?sepete=1")


def public_guest_cart(request):
    """Şifre gerektirmeyen müşteri sepeti."""
    cart = _guest_cart(request)
    items = []
    total_qty = 0
    for code, raw_qty in cart.items():
        try:
            qty = max(1, int(raw_qty))
        except (TypeError, ValueError):
            qty = 1
        product = UrunKod.objects.filter(kod__iexact=code, aktif=True).first()
        if not product:
            continue
        card = ProductCard.objects.filter(urun=product).first()
        items.append({"product": product, "card": card, "qty": qty})
        total_qty += qty
    return render(request, "product_cards/public_guest_cart.html", {
        "items": items,
        "total_qty": total_qty,
    })


@require_POST
def public_guest_cart_remove(request, code):
    cart = _guest_cart(request)
    cart.pop((code or "").strip().upper(), None)
    request.session[GUEST_CART_SESSION_KEY] = cart
    request.session.modified = True
    return redirect("public_guest_cart")


@require_POST
def public_guest_cart_clear(request):
    request.session.pop(GUEST_CART_SESSION_KEY, None)
    request.session.modified = True
    return redirect("public_guest_cart")
