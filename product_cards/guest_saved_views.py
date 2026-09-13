from django.core import signing
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .public_product_views import _cart_rows, _guest_cart


SAVED_SHEET_SALT = "moli.guest.saved.sheet.v1"


@require_POST
def guest_saved_sheet_create(request):
    cart = _guest_cart(request)
    if not cart:
        return redirect("public_guest_cart")

    token = signing.dumps(
        {"v": 1, "cart": cart},
        key=None,
        salt=SAVED_SHEET_SALT,
        compress=True,
    )
    return redirect("guest_saved_sheet", token=token)


def guest_saved_sheet(request, token):
    try:
        payload = signing.loads(token, salt=SAVED_SHEET_SALT)
    except signing.BadSignature:
        raise Http404("Föy bağlantısı geçersiz.")

    if not isinstance(payload, dict) or payload.get("v") != 1:
        raise Http404("Föy bağlantısı geçersiz.")

    cart = payload.get("cart")
    if not isinstance(cart, dict):
        raise Http404("Föy bağlantısı geçersiz.")

    items, total_qty = _cart_rows(cart)
    if not items:
        raise Http404("Bu föyde görüntülenecek ürün bulunamadı.")

    return render(request, "product_cards/public_guest_saved_sheet.html", {
        "items": items,
        "total_qty": total_qty,
        "share_url": request.build_absolute_uri(),
    })
