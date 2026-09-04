import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import Order, OrderEvent
from .models import ExchangeRate


FINANCE_STAGE = "finans_hareketi"

MOVEMENT_LABELS = {
    "INDIRIM": "İndirim",
    "EK_UCRET": "Ek ücret / fiyat artışı",
    "FIYAT_DUZELT": "Nihai satış fiyatını düzelt",
    "EK_MALIYET": "Ek maliyet",
    "KISMI_IADE": "Kısmi iade / iskonto",
    "IADE": "Tam iade",
    "KARGO_GERI": "Kargodan geri geldi",
    "YANLIS_SEVKIYAT": "Yanlış sevkiyat işlemi",
    "TEKRAR_SEVK": "Tekrar sevk edildi",
}

AMOUNT_REQUIRED = {"INDIRIM", "EK_UCRET", "FIYAT_DUZELT", "EK_MALIYET", "KISMI_IADE"}


def _can_manage(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


def _parse_decimal(value):
    text = (value or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError):
        raise ValueError("Geçerli bir tutar girin.")
    if amount < 0:
        raise ValueError("Tutar negatif olamaz.")
    return amount


def _to_tl(amount, currency, usd_try):
    if amount is None:
        return None
    if currency == "USD":
        return amount * usd_try if usd_try else None
    return amount


def _movement_payload(event):
    try:
        data = json.loads(event.new_value or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        data = {}
    data["event"] = event
    data["label"] = MOVEMENT_LABELS.get(event.value, event.value)
    return data


def calculate_finance_result(order):
    """Sevkiyat snapshot + sonraki hareketlerden güncel finansal sonucu üretir."""
    snapshot = getattr(order, "shipment_financial_snapshot", None)
    if not snapshot:
        return {
            "snapshot": None,
            "status": "SNAPSHOT_YOK",
            "status_label": "Sevkiyat finans kaydı yok",
            "is_final": False,
            "satis_tl": None,
            "maliyet_tl": None,
            "kar_tl": None,
            "kar_orani": None,
            "movements": [],
        }

    satis_tl = Decimal(snapshot.satis_tl or 0)
    maliyet_tl = Decimal(snapshot.toplam_maliyet_tl or 0)
    status = "SEVKEDILDI"
    status_label = "Sevk edildi"
    is_final = True

    events = order.events.filter(stage=FINANCE_STAGE).order_by("timestamp", "id")
    movements = []

    for event in events:
        data = _movement_payload(event)
        movements.append(data)
        movement_type = event.value
        tl_amount = Decimal(str(data.get("tl_amount") or "0"))

        if movement_type == "INDIRIM":
            satis_tl = max(Decimal("0"), satis_tl - tl_amount)
        elif movement_type == "EK_UCRET":
            satis_tl += tl_amount
        elif movement_type == "FIYAT_DUZELT":
            satis_tl = max(Decimal("0"), tl_amount)
        elif movement_type == "EK_MALIYET":
            maliyet_tl += tl_amount
        elif movement_type == "KISMI_IADE":
            satis_tl = max(Decimal("0"), satis_tl - tl_amount)
        elif movement_type == "IADE":
            satis_tl = Decimal("0")
            status = "IADE"
            status_label = "Tam iade"
            is_final = True
        elif movement_type == "KARGO_GERI":
            status = "KARGO_GERI"
            status_label = "Kargodan geri geldi — yeniden sevk bekleniyor"
            is_final = False
        elif movement_type == "YANLIS_SEVKIYAT":
            status = "YANLIS_SEVKIYAT"
            status_label = "Yanlış sevkiyat işlemi — finans sonucu beklemede"
            is_final = False
        elif movement_type == "TEKRAR_SEVK":
            status = "SEVKEDILDI"
            status_label = "Tekrar sevk edildi"
            is_final = True

    kar_tl = satis_tl - maliyet_tl
    kar_orani = (kar_tl / satis_tl * Decimal("100")) if satis_tl else None

    return {
        "snapshot": snapshot,
        "status": status,
        "status_label": status_label,
        "is_final": is_final,
        "satis_tl": satis_tl.quantize(Decimal("0.01")),
        "maliyet_tl": maliyet_tl.quantize(Decimal("0.01")),
        "kar_tl": kar_tl.quantize(Decimal("0.01")),
        "kar_orani": kar_orani.quantize(Decimal("0.01")) if kar_orani is not None else None,
        "movements": movements,
    }


@login_required
def order_finance_movements(request, order_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    order = get_object_or_404(Order.objects.select_related("musteri"), pk=order_id)
    result = calculate_finance_result(order)
    return render(request, "product_cards/order_finance_movements.html", {
        "order": order,
        "result": result,
        "movement_labels": MOVEMENT_LABELS,
    })


@login_required
@require_POST
def add_order_finance_movement(request, order_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu işlemi yapma yetkiniz yok.")

    order = get_object_or_404(Order, pk=order_id)
    movement_type = (request.POST.get("movement_type") or "").strip()
    if movement_type not in MOVEMENT_LABELS:
        messages.error(request, "Geçersiz finans hareketi.")
        return redirect("order_finance_movements", order_id=order.id)

    currency = (request.POST.get("currency") or "TRY").strip().upper()
    if currency not in {"TRY", "USD"}:
        currency = "TRY"

    try:
        amount = _parse_decimal(request.POST.get("amount"))
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("order_finance_movements", order_id=order.id)

    if movement_type in AMOUNT_REQUIRED and amount is None:
        messages.error(request, "Bu işlem için tutar girmelisiniz.")
        return redirect("order_finance_movements", order_id=order.id)

    rate_obj = ExchangeRate.objects.order_by("-rate_date", "-fetched_at").first()
    usd_try = rate_obj.usd_try if rate_obj else None
    tl_amount = _to_tl(amount, currency, usd_try) if amount is not None else Decimal("0")

    payload = {
        "amount": str(amount) if amount is not None else None,
        "currency": currency,
        "usd_try": str(usd_try) if usd_try is not None else None,
        "tl_amount": str(tl_amount.quantize(Decimal("0.01"))) if tl_amount is not None else "0.00",
        "note": (request.POST.get("note") or "").strip(),
    }

    OrderEvent.objects.create(
        order=order,
        user=request.user.username,
        gorev="yok",
        stage=FINANCE_STAGE,
        value=movement_type,
        aciklama=payload["note"],
        event_type="stage",
        new_value=json.dumps(payload, ensure_ascii=False),
    )

    messages.success(request, f"{MOVEMENT_LABELS[movement_type]} kaydedildi. Önceki finans kayıtları değiştirilmedi.")
    return redirect("order_finance_movements", order_id=order.id)
