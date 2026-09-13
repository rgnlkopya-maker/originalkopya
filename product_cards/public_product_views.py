import io
import secrets
from decimal import Decimal, InvalidOperation

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


def _manager_user(user):
    return bool(user.is_authenticated and user.groups.filter(name__in=["patron", "mudur"]).exists())


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


def _normalize_rows(value):
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        rows = value.get("rows") or []
    elif isinstance(value, list):
        rows = value
    else:
        try:
            qty = max(1, int(value or 1))
        except (TypeError, ValueError):
            qty = 1
        rows = [{"color": "", "size": "", "quantity": qty, "description": ""}]
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            qty = max(1, int(row.get("quantity") or row.get("adet") or 1))
        except (TypeError, ValueError):
            qty = 1
        result.append({
            "color": str(row.get("color") or row.get("renk") or "").strip(),
            "size": str(row.get("size") or row.get("beden") or "").strip(),
            "quantity": qty,
            "description": str(row.get("description") or row.get("aciklama") or "").strip(),
        })
    return result or [{"color": "", "size": "", "quantity": 1, "description": ""}]


def _guest_cart_count(request):
    total = 0
    for value in _guest_cart(request).values():
        total += sum(r["quantity"] for r in _normalize_rows(value))
    return total


def _transfer_valid(transfer):
    return isinstance(transfer, dict) and not transfer.get("used") and bool(transfer.get("token"))


def _cart_rows(cart):
    items = []
    total_qty = 0
    if not isinstance(cart, dict):
        return items, total_qty
    for code, raw_value in cart.items():
        product = UrunKod.objects.filter(kod__iexact=code, aktif=True).first()
        if not product:
            continue
        card = ProductCard.objects.filter(urun=product).first()
        rows = _normalize_rows(raw_value)
        qty = sum(r["quantity"] for r in rows)
        items.append({"product": product, "card": card, "qty": qty, "rows": rows})
        total_qty += qty
    return items, total_qty


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
    ShowroomDraftItem.objects.create(draft=draft, product_card=card, color=color, size=size, description="", quantity=quantity, unit_price=price_row.get("cash") or Decimal("0"))
    suffix = "&detayli=1" if mode == "detailed" else ""
    return redirect(f"/urun-kartlari/qr/urun/{product.kod}/?eklendi=1{suffix}")


@require_POST
def public_product_add_to_cart(request, code):
    if _manager_user(request.user):
        return HttpResponseForbidden("Müdür/patron hesabında ürünleri Sipariş Föyüne ekleyin.")
    product = _test_product(code)
    if not ProductCard.objects.filter(urun=product, price_list_active=True).exists():
        raise Http404("Bu ürün aktif değil.")

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


def public_guest_cart(request):
    items, total_qty = _cart_rows(_guest_cart(request))
    transfer = request.session.get(GUEST_TRANSFER_SESSION_KEY)
    return render(request, "product_cards/public_guest_cart.html", {"items": items, "total_qty": total_qty, "transfer": transfer if _transfer_valid(transfer) else None})


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
    transfer = {"code": f"{secrets.randbelow(900000) + 100000}", "token": secrets.token_urlsafe(24), "cart": dict(cart), "created_at": timezone.now().isoformat(), "used": False}
    request.session[GUEST_TRANSFER_SESSION_KEY] = transfer
    request.session.modified = True
    return redirect("public_guest_cart")


def public_guest_transfer_qr(request):
    transfer = request.session.get(GUEST_TRANSFER_SESSION_KEY)
    if not _transfer_valid(transfer) or not request.session.session_key:
        raise Http404("Aktarım kodu bulunamadı veya artık geçerli değil.")
    url = request.build_absolute_uri(f"/urun-kartlari/qr/sepet-aktar/{request.session.session_key}/{transfer['token']}/")
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
        raise Http404("Aktarım kodu geçersiz veya artık kullanılamıyor.")
    items, total_qty = _cart_rows(transfer.get("cart", {}))
    return render(request, "product_cards/public_guest_transfer_preview.html", {
        "items": items,
        "total_qty": total_qty,
        "transfer_code": transfer.get("code"),
        "session_key": session_key,
        "token": token,
    })


@login_required
@require_POST
def staff_guest_transfer_to_sheet(request, session_key, token):
    if not _manager_user(request.user):
        return HttpResponseForbidden("Bu işlem yalnızca müdür/patron içindir.")
    session, transfer = _load_transfer(session_key, token)
    if not transfer:
        raise Http404("Aktarım kodu geçersiz veya daha önce kullanılmış.")

    items, total_qty = _cart_rows(transfer.get("cart", {}))
    if not items:
        raise Http404("Aktarılacak ürün bulunamadı.")

    prices = {}
    price_error = ""
    for item in items:
        code = item["product"].kod
        raw = (request.POST.get(f"price_{code}") or "").strip().replace(",", ".")
        try:
            price = Decimal(raw)
            if price < 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            price_error = f"{code} için anlaşılan fiyatı girin."
            break
        prices[code] = price

    if price_error:
        return render(request, "product_cards/public_guest_transfer_preview.html", {
            "items": items,
            "total_qty": total_qty,
            "transfer_code": transfer.get("code"),
            "session_key": session_key,
            "token": token,
            "price_error": price_error,
            "entered_prices": request.POST,
        })

    draft = _active_draft(request.user) or _create_draft(request.user)
    added = 0
    for item in items:
        card = item["card"]
        if not card or not card.price_list_active:
            continue
        unit_price = prices[item["product"].kod]
        for row in item["rows"]:
            ShowroomDraftItem.objects.create(
                draft=draft,
                product_card=card,
                color=row["color"],
                size=row["size"],
                description=row["description"],
                quantity=row["quantity"],
                unit_price=unit_price,
            )
            added += row["quantity"]

    if not added:
        raise Http404("Sepette aktarılabilecek ürün bulunamadı.")

    data = session.get_decoded()
    transfer["used"] = True
    transfer["used_at"] = timezone.now().isoformat()
    transfer["used_by"] = request.user.id
    data[GUEST_TRANSFER_SESSION_KEY] = transfer
    data[GUEST_CART_SESSION_KEY] = {}
    session.session_data = Session.objects.encode(data)
    session.save(update_fields=["session_data"])
    return redirect("showroom_page")


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
