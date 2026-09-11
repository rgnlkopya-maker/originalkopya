import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from core.models import Beden, Musteri, Renk, URUN_TIPI_CHOICES, UrunKod
from .models import PriceListSettings, ProductCard, ShowroomDraft, ShowroomDraftItem
from .price_list_views import _can_manage, _ensure_price_rates, _price_rows, _real_profit_rate


def _active_draft(user):
    return ShowroomDraft.objects.filter(created_by=user, status="DRAFT").order_by("-updated_at", "-id").first()


def _decimal(value, default="0"):
    try:
        return Decimal(str(value if value not in (None, "") else default))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _create_draft(user, customer=None):
    settings = PriceListSettings.get_solo()
    return ShowroomDraft.objects.create(
        created_by=user,
        customer=customer,
        status="DRAFT",
        currency="TRY",
        profit_rate=settings.profit_rate,
        discount_rate=Decimal("0"),
        monthly_term_rate=settings.monthly_term_rate,
        usd_try=settings.usd_try,
        eur_try=settings.eur_try,
        overall_discount_amount=Decimal("0"),
    )


def _serialize_draft(draft):
    if not draft:
        return {
            "ok": True,
            "draft": None,
            "customer_id": "",
            "items": [],
            "discount_rate": "0",
            "discount_amount": "0",
        }

    groups = []
    group_map = {}
    row_maps = {}
    items = draft.items.select_related("product_card__urun").order_by("created_at", "id")

    for db_item in items:
        code = db_item.product_card.urun.kod
        unit_price = str(db_item.unit_price)
        group_key = (db_item.product_card_id, unit_price)
        if group_key not in group_map:
            group = {
                "urun_kodu": code,
                "anlasilan_fiyat": unit_price,
                "satirlar": [],
            }
            group_map[group_key] = len(groups)
            groups.append(group)
            row_maps[group_key] = {}

        group = groups[group_map[group_key]]
        row_key = (db_item.color, db_item.quantity, db_item.description)
        rows_for_group = row_maps[group_key]
        if row_key not in rows_for_group:
            row = {
                "renk": db_item.color,
                "bedenler": [],
                "adet": db_item.quantity,
                "aciklama": db_item.description,
            }
            rows_for_group[row_key] = len(group["satirlar"])
            group["satirlar"].append(row)
        group["satirlar"][rows_for_group[row_key]]["bedenler"].append(db_item.size)

    return {
        "ok": True,
        "draft": draft.id,
        "customer_id": str(draft.customer_id or ""),
        "items": groups,
        "discount_rate": str(draft.discount_rate or 0),
        "discount_amount": str(draft.overall_discount_amount or 0),
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }


@login_required
def showroom_page(request):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    settings = PriceListSettings.get_solo()
    if settings.profit_rate <= 0 and settings.discount_rate > 0:
        settings.discount_rate = Decimal("0")
        settings.save(update_fields=["discount_rate", "updated_at"])

    rate_error = _ensure_price_rates(settings)
    show_inactive = request.GET.get("durum") == "pasif"
    musteriler = Musteri.objects.filter(aktif=True).order_by("ad")
    renkler = Renk.objects.filter(aktif=True).order_by("ad")
    bedenler = Beden.objects.filter(aktif=True).order_by("ad")
    urun_kodlari = UrunKod.objects.filter(aktif=True).order_by("kod")

    return render(request, "product_cards/showroom_page.html", {
        "settings": settings,
        "rows": _price_rows(settings, active=not show_inactive),
        "show_inactive": show_inactive,
        "inactive_count": ProductCard.objects.filter(price_list_active=False).count(),
        "rate_error": rate_error,
        "real_profit_rate": _real_profit_rate(settings.profit_rate, settings.discount_rate),
        "showroom_mode": True,
        "musteriler": musteriler,
        "renkler": renkler,
        "bedenler": bedenler,
        "urun_kodlari": urun_kodlari,
        "aktif_musteriler": musteriler,
        "aktif_renkler": renkler,
        "aktif_bedenler": bedenler,
        "aktif_urun_kodlari": urun_kodlari,
        "urun_tipi_secenekleri": URUN_TIPI_CHOICES,
    })


@login_required
@require_GET
def showroom_draft_load(request):
    if not _can_manage(request.user):
        return JsonResponse({"ok": False, "message": "Yetkiniz yok."}, status=403)
    return JsonResponse(_serialize_draft(_active_draft(request.user)))


@login_required
@require_POST
def showroom_draft_autosave(request):
    if not _can_manage(request.user):
        return JsonResponse({"ok": False, "message": "Yetkiniz yok."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "message": "Geçersiz veri."}, status=400)

    customer_id = payload.get("customer_id") or None
    raw_items = payload.get("items") or []
    if not isinstance(raw_items, list):
        return JsonResponse({"ok": False, "message": "Ürün verisi geçersiz."}, status=400)

    customer = Musteri.objects.filter(pk=customer_id).first() if customer_id else None

    with transaction.atomic():
        draft = _active_draft(request.user) or _create_draft(request.user, customer)
        draft.customer = customer
        draft.save(update_fields=["customer", "updated_at"])

        draft.items.all().delete()
        create_rows = []

        for item in raw_items:
            code = str(item.get("urun_kodu") or "").strip()
            if not code:
                continue
            product_card = ProductCard.objects.select_related("urun").filter(urun__kod__iexact=code).first()
            if not product_card:
                continue
            unit_price = max(Decimal("0"), _decimal(item.get("anlasilan_fiyat"), "0"))
            satirlar = item.get("satirlar") or []
            if not isinstance(satirlar, list):
                continue

            for row in satirlar:
                color = str(row.get("renk") or "")[:120]
                description = str(row.get("aciklama") or "")[:500]
                try:
                    quantity = max(1, int(row.get("adet") or 1))
                except (TypeError, ValueError):
                    quantity = 1
                sizes = row.get("bedenler") or []
                if not isinstance(sizes, list):
                    sizes = []
                for size in sizes:
                    create_rows.append(ShowroomDraftItem(
                        draft=draft,
                        product_card=product_card,
                        color=color,
                        size=str(size or "")[:120],
                        description=description,
                        quantity=quantity,
                        unit_price=unit_price,
                    ))

        if create_rows:
            ShowroomDraftItem.objects.bulk_create(create_rows)

    return JsonResponse({
        "ok": True,
        "draft": draft.id,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    })


@login_required
@require_POST
def showroom_draft_discount_save(request):
    if not _can_manage(request.user):
        return JsonResponse({"ok": False, "message": "Yetkiniz yok."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "message": "Geçersiz veri."}, status=400)

    discount_rate = max(Decimal("0"), min(Decimal("100"), _decimal(payload.get("discount_rate"), "0")))
    discount_amount = max(Decimal("0"), _decimal(payload.get("discount_amount"), "0"))

    draft = _active_draft(request.user) or _create_draft(request.user)
    draft.discount_rate = discount_rate
    draft.overall_discount_amount = discount_amount
    draft.save(update_fields=["discount_rate", "overall_discount_amount", "updated_at"])

    return JsonResponse({
        "ok": True,
        "draft": draft.id,
        "discount_rate": str(draft.discount_rate),
        "discount_amount": str(draft.overall_discount_amount),
    })
