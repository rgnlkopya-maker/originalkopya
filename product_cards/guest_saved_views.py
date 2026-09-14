from django.contrib.auth.decorators import login_required
from django.core import signing
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import ShowroomDraft
from .price_list_views import _can_manage
from .public_product_views import _cart_rows, _guest_cart
from .showroom_views import _draft_summary, _payment_rows, _serialize_draft


SAVED_SHEET_SALT = "moli.guest.saved.sheet.v1"
DRAFT_SHARE_SALT = "moli.showroom.public.share.v1"


@require_POST
def guest_saved_sheet_create(request):
    cart = _guest_cart(request)
    if not cart:
        return redirect("public_guest_cart")

    token = signing.dumps(
        {"v": 1, "cart": cart},
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


@login_required
def staff_draft_share(request, draft_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")

    draft = get_object_or_404(
        ShowroomDraft,
        id=draft_id,
        created_by=request.user,
        status__in=["PENDING", "APPROVED", "TRANSFERRED"],
    )
    token = signing.dumps(
        {"v": 1, "draft_id": draft.id},
        salt=DRAFT_SHARE_SALT,
        compress=True,
    )
    return redirect("public_draft_sheet", token=token)


def public_draft_sheet(request, token):
    try:
        payload = signing.loads(token, salt=DRAFT_SHARE_SALT)
    except signing.BadSignature:
        raise Http404("Föy bağlantısı geçersiz.")

    if not isinstance(payload, dict) or payload.get("v") != 1:
        raise Http404("Föy bağlantısı geçersiz.")

    draft_id = payload.get("draft_id")
    draft = get_object_or_404(
        ShowroomDraft.objects.select_related("customer").prefetch_related(
            "items__product_card__urun", "payments"
        ),
        id=draft_id,
        status__in=["PENDING", "APPROVED", "TRANSFERRED"],
    )

    data = _serialize_draft(draft)
    summary = _draft_summary(draft)
    if draft.status == "PENDING":
        status_label = "Taslak Teklif"
    elif draft.status == "TRANSFERRED":
        status_label = "Siparişe Dönüştürüldü"
    else:
        status_label = "Onaylanan Föy"

    return render(request, "product_cards/public_shared_draft.html", {
        "draft": draft,
        "items": data["items"],
        "summary": summary,
        "payments": _payment_rows(draft),
        "status_label": status_label,
        "share_url": request.build_absolute_uri(),
    })
