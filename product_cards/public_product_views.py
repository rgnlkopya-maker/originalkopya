import io
import secrets
from datetime import timedelta
from decimal import Decimal

import qrcode
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Beden, Renk, UrunKod
from .models import PriceListSettings, ProductCard, ShowroomDraftItem
from .price_list_views import _price_rows
from .showroom_views import _active_draft, _create_draft


TEST_PUBLIC_PRODUCT_CODE = "7167"
GUEST_CART_SESSION_KEY = "moli_guest_showroom_cart_v1"
GUEST_TRANSFER_SESSION_KEY = "moli_guest_cart_transfer_v1"
TRANSFER_TTL_MINUTES = 30


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
    total = 0
    for qty in _guest_cart(request).values():
        try:
            total += max(0, int(qty))
        except (TypeError, ValueError):
            pass
    return total


def _transfer_valid(transfer):
    if not isinstance(transfer, dict) or transfer.get("used"):
        return False
    raw_expiry = transfer.get("expires_at")
    if not raw_expiry:
        return False
    try:
        expiry = timezone.datetime.fromisoformat(raw_expiry)
        if timezone.is_naive(expiry):
            expiry = timezone.make_aware(expiry)
    except (TypeError, ValueError):
        return False
    return expiry > timezone.now()


def _cart_rows(cart):
    rows = []
    total_qty = 0
    if not isinstance(cart, dict):
        return rows, total_qty
    for code, raw_qty in cart.items():
        try:
            qty = max(1, int(raw_qty))
        except (TypeError, ValueError):
            qty = 1
        product = UrunKod.objects.filter(kod__iexact=code, aktif=True).first()
        if not product:
            continue
        card = ProductCard.objects.filter(urun=product).first()
        rows.append({"product": product, "card": card, "qty": qty})
        total_qty += qty
    return rows, total_qty


def public_product_page(request, code):
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
    if _manager_user(request.user):
        return HttpResponseForbidden("Müdür/patron hesabında ürünleri Sipariş Föyüne ekleyin.")
    product = _test_product(code)
    if not ProductCard.objects.filter(urun=product, price_list_active=True).exists():
        raise Http404("Bu ürün aktif değil.")

    cart = _guest_cart(request)
    try:
        current = int(cart.get(product.kod, 0))
    except (TypeError, ValueError):
        current = 0
    cart[product.kod] = max(0, current) + 1
    request.session[GUEST_CART_SESSION_KEY] = cart
    request.session.modified = True
    return redirect(f"/urun-kartlari/qr/urun/{product.kod}/?sepete=1")


def public_guest_cart(request):
    items, total_qty = _cart_rows(_guest_cart(request))
    transfer = request.session.get(GUEST_TRANSFER_SESSION_KEY)
    return render(request, "product_cards/public_guest_cart.html", {
        "items": items,
        "total_qty": total_qty,
        "transfer": transfer if _transfer_valid(transfer) else None,
    })


@require_POST
def public_guest_cart_remove(request, code):
    cart = _guest_cart(request)
    cart.pop((code or "").strip().upper(), None)
    request.session[GUEST_CART_SESSION_KEY] = cart
    request.session.pop(GUEST_TRANSFER_SESSION_KEY, None)
    request.session.modified = True
    return redirect("public_guest_cart")


@require_POST
def public_guest_cart_clear(request):
    request.session.pop(GUEST_CART_SESSION_KEY, None)
    request.session.pop(GUEST_TRANSFER_SESSION_KEY, None)
    request.session.modified = True
    return redirect("public_guest_cart")


@require_POST
def public_guest_transfer_create(request):
    cart = _guest_cart(request)
    if not cart:
        return redirect("public_guest_cart")
    if not request.session.session_key:
        request.session.save()
    transfer = {
        "code": f"{secrets.randbelow(900000) + 100000}",
        "token": secrets.token_urlsafe(24),
        "cart": dict(cart),
        "created_at": timezone.now().isoformat(),
        "expires_at": (timezone.now() + timedelta(minutes=TRANSFER_TTL_MINUTES)).isoformat(),
        "used": False,
    }
    request.session[GUEST_TRANSFER_SESSION_KEY] = transfer
    request.session.modified = True
    return redirect("public_guest_cart")


def public_guest_transfer_qr(request):
    transfer = request.session.get(GUEST_TRANSFER_SESSION_KEY)
    if not _transfer_valid(transfer) or not request.session.session_key:
        raise Http404("Aktarım kodu bulunamadı veya süresi doldu.")
    url = request.build_absolute_uri(
        f"/urun-kartlari/qr/sepet-aktar/{request.session.session_key}/{transfer['token']}/"
    )
    image = qrcode.make(url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


def _load_transfer(session_key, token=None):
    try:
        session = Session.objects.get(session_key=session_key, expire_date__gt=timezone.now())
    except Session.DoesNotExist:
        return None, None
    data = session.get_decoded()
    transfer = data.get(GUEST_TRANSFER_SESSION_KEY)
    if not _transfer_valid(transfer):
        return None, None
    if token is not None and not secrets.compare_digest(str(transfer.get("token", "")), str(token)):
        return None, None
    return session, transfer


@login_required
def staff_guest_transfer_preview(request, session_key, token):
    if not _manager_user(request.user):
        return HttpResponseForbidden("Bu ekran yalnızca müdür/patron içindir.")
    _, transfer = _load_transfer(session_key, token)
    if not transfer:
        raise Http404("Aktarım kodu geçersiz veya süresi dolmuş.")
    items, total_qty = _cart_rows(transfer.get("cart", {}))
    return render(request, "product_cards/public_guest_transfer_preview.html", {
        "items": items,
        "total_qty": total_qty,
        "transfer_code": transfer.get("code"),
        "expires_at": transfer.get("expires_at"),
        "session_key": session_key,
        "token": token,
    })


@login_required
def staff_guest_transfer_code(request):
    if not _manager_user(request.user):
        return HttpResponseForbidden("Bu ekran yalnızca müdür/patron içindir.")
    error = ""
    if request.method == "POST":
        code = "".join(ch for ch in (request.POST.get("code") or "") if ch.isdigit())[:6]
        if len(code) == 6:
            for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
                data = session.get_decoded()
                transfer = data.get(GUEST_TRANSFER_SESSION_KEY)
                if _transfer_valid(transfer) and str(transfer.get("code")) == code:
                    return redirect("staff_guest_transfer_preview", session_key=session.session_key, token=transfer.get("token"))
        error = "Aktif bir sepet bulunamadı. Kodu kontrol edin veya müşteriden yeni kod oluşturmasını isteyin."
    return render(request, "product_cards/public_guest_transfer_code.html", {"error": error})
