import io
from decimal import Decimal

import qrcode
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.models import Beden, Renk, UrunKod
from .models import PriceListSettings, ProductCard, ShowroomDraftItem
from .price_list_views import _can_manage, _price_rows
from .showroom_views import _active_draft, _create_draft
from .public_product_views import (
    GUEST_CART_SESSION_KEY,
    GUEST_TRANSFER_SESSION_KEY,
    _guest_cart,
    _guest_cart_count,
    _manager_user,
    _normalize_rows,
)


def _active_product(code):
    normalized = (code or "").strip().upper()
    product = UrunKod.objects.filter(kod__iexact=normalized, aktif=True).first()
    if not product:
        raise Http404("Ürün bulunamadı.")
    card = ProductCard.objects.filter(urun=product, price_list_active=True).first()
    if not card:
        raise Http404("Bu ürün aktif değil.")
    return product, card


def _card_for_qr(card_id):
    return ProductCard.objects.select_related("urun").filter(id=card_id).first()


def _product_public_url(request, card):
    path = reverse("public_product_page", args=[card.urun.kod])
    return request.build_absolute_uri(path)


def public_product_page(request, code):
    product, card = _active_product(code)
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


@login_required
def product_qr_png(request, card_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")
    card = _card_for_qr(card_id)
    if not card:
        raise Http404("Ürün kartı bulunamadı.")
    image = qrcode.make(_product_public_url(request, card))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="moli-{card.urun.kod}-qr.png"'
    return response


@login_required
def product_qr_download(request, card_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")
    card = _card_for_qr(card_id)
    if not card:
        raise Http404("Ürün kartı bulunamadı.")
    image = qrcode.make(_product_public_url(request, card))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="moli-{card.urun.kod}-qr.png"'
    return response


@login_required
def product_qr_label(request, card_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")
    card = _card_for_qr(card_id)
    if not card:
        raise Http404("Ürün kartı bulunamadı.")
    return render(request, "product_cards/product_qr_label.html", {
        "card": card,
        "public_url": _product_public_url(request, card),
    })


@require_POST
def public_product_add_to_sheet(request, code):
    if not _manager_user(request.user):
        return HttpResponseForbidden("Bu işlem için müdür veya patron girişi gerekir.")
    product, card = _active_product(code)
    settings = PriceListSettings.get_solo()
    price_row = next((row for row in _price_rows(settings, active=True) if row["id"] == card.id), None)
    if not price_row:
        raise Http404("Ürün fiyatı bulunamadı.")

    mode = (request.POST.get("mode") or "quick").strip().lower()
    color = ""
    size = ""
    quantity = 1
    description = ""
    if mode == "detailed":
        color = (request.POST.get("renk") or "").strip()
        size = (request.POST.get("beden") or "").strip()
        description = (request.POST.get("aciklama") or "").strip()
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
        description=description,
        quantity=quantity,
        unit_price=price_row.get("cash") or Decimal("0"),
    )
    suffix = "&detayli=1" if mode == "detailed" else ""
    return redirect(f"/urun-kartlari/qr/urun/{product.kod}/?eklendi=1{suffix}")


@require_POST
def public_product_add_to_cart(request, code):
    if _manager_user(request.user):
        return HttpResponseForbidden("Müdür/patron hesabında ürünleri Sipariş Föyüne ekleyin.")
    product, _ = _active_product(code)

    colors = request.POST.getlist("renk")
    sizes = request.POST.getlist("beden")
    quantities = request.POST.getlist("adet")
    descriptions = request.POST.getlist("aciklama")
    row_count = max(len(colors), len(sizes), len(quantities), len(descriptions), 1)
    new_rows = []
    for i in range(row_count):
        color = (colors[i] if i < len(colors) else "").strip()
        size = (sizes[i] if i < len(sizes) else "").strip()
        desc = (descriptions[i] if i < len(descriptions) else "").strip()
        try:
            qty = max(1, int(quantities[i] if i < len(quantities) else 1))
        except (TypeError, ValueError):
            qty = 1
        if color and not Renk.objects.filter(ad__iexact=color, aktif=True).exists():
            color = ""
        if size and not Beden.objects.filter(ad__iexact=size, aktif=True).exists():
            size = ""
        new_rows.append({"color": color, "size": size, "quantity": qty, "description": desc})

    cart = _guest_cart(request)
    existing = _normalize_rows(cart.get(product.kod, {"rows": []})) if product.kod in cart else []
    cart[product.kod] = {"rows": existing + new_rows}
    request.session[GUEST_CART_SESSION_KEY] = cart
    request.session.pop(GUEST_TRANSFER_SESSION_KEY, None)
    request.session.modified = True
    return redirect(f"/urun-kartlari/qr/urun/{product.kod}/?sepete=1")
