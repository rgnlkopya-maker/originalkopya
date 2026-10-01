from collections import defaultdict

from app_settings.access import data_scope_value
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import timedelta

from .models import Order, OrderEvent, ProductionStageControlExclusion


STAGES = {
    "kesim": ("kesim_durum", "Kesim"),
    "dikim": ("dikim_durum", "Dikim"),
    "susleme": ("susleme_durum", "Süsleme"),
}

REQUIRED_VALUES = ("basladi", "bitti")


def _has_stage_evidence(events, *stage_names):
    return any(event.stage in stage_names for event in events)


def _missing_stage_steps(events, stage_name, label):
    values = {event.value for event in events if event.stage == stage_name}
    missing = []
    if "basladi" not in values:
        missing.append(f"{label} Başladı")
    if "bitti" not in values:
        missing.append(f"{label} Bitti")
    return missing


def get_unshipped_inactive_orders(user):
    """Üretim Aşama Kontrolü ile aynı 3+ gün hareketsiz listesini üret."""
    orders = (
        Order.objects.select_related("musteri")
        .filter(is_active=True)
        .exclude(siparis_tipi="MALZEME")
        .only(
            "id", "siparis_numarasi", "musteri__ad", "urun_kodu", "renk",
            "beden", "siparis_tipi", "is_active", "sevkiyat_durum"
        )
        .order_by("-id")
    )
    if data_scope_value(user, "orders") == "active_only":
        orders = orders.filter(is_active=True)

    order_ids = list(orders.values_list("id", flat=True))
    events_by_order = defaultdict(list)
    relevant_stages = {
        "malzeme_durum",
        "kesim_durum",
        "dikim_durum", "dikim_fason_durumu",
        "nakis_durum",
        "susleme_durum", "susleme_fason_durumu",
        "hazir_durum",
        "uretim_aktarimi", "uretim_aktarimı",
        "sevkiyat_durum",
    }
    for event in (
        OrderEvent.objects.filter(
            order_id__in=order_ids,
            event_type="stage",
            stage__in=relevant_stages,
        )
        .only("order_id", "stage", "value", "timestamp", "user")
        .order_by("order_id", "timestamp", "id")
    ):
        events_by_order[event.order_id].append(event)

    now = timezone.now()
    ProductionStageControlExclusion.objects.filter(
        control_type="unshipped_3d_temp",
        excluded_at__lte=now - timedelta(days=3),
    ).delete()
    exclusions = {
        (row.order_id, row.control_type)
        for row in ProductionStageControlExclusion.objects.all().only("order_id", "control_type")
    }

    rows = []
    for order in orders:
        events = events_by_order.get(order.id, [])
        if not events:
            continue
        shipment_events = [event for event in events if event.stage == "sevkiyat_durum"]
        shipped = (
            shipment_events[-1].value == "gonderildi"
            if shipment_events
            else order.sevkiyat_durum == "gonderildi"
        )
        temporarily_hidden = (order.id, "unshipped_3d_temp") in exclusions
        permanently_hidden = (order.id, "unshipped_7d") in exclusions
        if not shipped and not temporarily_hidden and not permanently_hidden:
            last_event = events[-1]
            age = now - last_event.timestamp
            if age >= timedelta(days=3):
                rows.append({
                    "order": order,
                    "first_event": events[0],
                    "last_event": last_event,
                    "days_open": age.days,
                })
    rows.sort(key=lambda row: (-row["days_open"], row["first_event"].timestamp))
    return rows


@login_required
@require_POST
def exclude_from_production_stage_control(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    control_type = (request.POST.get("control_type") or "").strip()
    valid_types = {value for value, _label in ProductionStageControlExclusion.CONTROL_TYPES}
    if control_type not in valid_types:
        return redirect("production_stage_control")

    hide_days = (request.POST.get("hide_days") or "").strip()
    if control_type == "unshipped_7d" and hide_days == "3":
        control_type = "unshipped_3d_temp"

    ProductionStageControlExclusion.objects.update_or_create(
        order=order,
        control_type=control_type,
        defaults={"excluded_by": request.user, "excluded_at": timezone.now()},
    )
    return redirect(request.POST.get("next") or "production_stage_control")


@login_required
@require_POST
def restore_to_production_stage_control(request, exclusion_id):
    exclusion = get_object_or_404(ProductionStageControlExclusion, pk=exclusion_id)
    exclusion.delete()
    target = request.POST.get("next")
    if target:
        return redirect(target)
    return redirect("/uretim-asama-kontrolu/?section=problems&excluded=1")


@login_required
def production_stage_control(request):
    """Üretimde sonraki aşamaya geçildiği halde eksik bırakılmış aşama kayıtlarını göster."""
    orders = (
        Order.objects.select_related("musteri")
        .filter(is_active=True)
        .exclude(siparis_tipi="MALZEME")
        .only(
            "id", "siparis_numarasi", "musteri__ad", "urun_kodu", "renk",
            "beden", "siparis_tipi", "is_active", "sevkiyat_durum"
        )
        .order_by("-id")
    )
    if data_scope_value(request.user, "orders") == "active_only":
        orders = orders.filter(is_active=True)

    order_ids = list(orders.values_list("id", flat=True))
    events_by_order = defaultdict(list)
    relevant_stages = {
        "malzeme_durum",
        "kesim_durum",
        "dikim_durum", "dikim_fason_durumu",
        "nakis_durum",
        "susleme_durum", "susleme_fason_durumu",
        "hazir_durum",
        "uretim_aktarimi", "uretim_aktarimı",
        "sevkiyat_durum",
    }
    for event in (
        OrderEvent.objects.filter(
            order_id__in=order_ids,
            event_type="stage",
            stage__in=relevant_stages,
        )
        .only("order_id", "stage", "value", "timestamp", "user")
        .order_by("order_id", "timestamp", "id")
    ):
        events_by_order[event.order_id].append(event)

    now = timezone.now()
    ProductionStageControlExclusion.objects.filter(
        control_type="unshipped_3d_temp",
        excluded_at__lte=now - timedelta(days=3),
    ).delete()

    exclusions = {
        (row.order_id, row.control_type)
        for row in ProductionStageControlExclusion.objects.all().only("order_id", "control_type")
    }

    problems = []
    unshipped_after_week = get_unshipped_inactive_orders(request.user)
    for order in orders:
        events = events_by_order.get(order.id, [])
        if not events:
            continue

        reasons = []

        # Dikimle ilgili herhangi bir işlem yapıldıysa kesim zinciri tamamlanmış olmalı.
        if _has_stage_evidence(events, "dikim_durum", "dikim_fason_durumu"):
            reasons.extend(_missing_stage_steps(events, "kesim_durum", "Kesim"))

        # Süsleme ile ilgili herhangi bir işlem yapıldıysa dikim zinciri tamamlanmış olmalı.
        if _has_stage_evidence(events, "susleme_durum", "susleme_fason_durumu"):
            reasons.extend(_missing_stage_steps(events, "dikim_durum", "Dikim"))

        # Hazır aşamasına dokunulduysa süsleme zinciri tamamlanmış olmalı.
        if _has_stage_evidence(events, "hazir_durum"):
            reasons.extend(_missing_stage_steps(events, "susleme_durum", "Süsleme"))

        # Güncel sevkiyat durumunu son sevkiyat hareketinden belirle.
        shipment_events = [event for event in events if event.stage == "sevkiyat_durum"]
        shipped = (
            shipment_events[-1].value == "gonderildi"
            if shipment_events
            else order.sevkiyat_durum == "gonderildi"
        )
        if shipped:
            for stage_name, label in STAGES.values():
                reasons.extend(_missing_stage_steps(events, stage_name, label))

        # Aynı eksikliği birden fazla kural yakalasa bile ekranda bir kez göster.
        reasons = list(dict.fromkeys(reasons))
        if reasons and (order.id, "stage_problem") not in exclusions:
            last_event = events[-1]
            problems.append({
                "order": order,
                "reasons": reasons,
                "last_event": last_event,
                "shipped": shipped,
            })

    problems.sort(
        key=lambda row: (not row["shipped"], -row["last_event"].timestamp.timestamp())
    )

    order_type = (request.GET.get("order_type") or "ALL").strip().upper()
    valid_order_types = {"ALL", "OZEL", "SERI", "TEKLI", "STOK", "KONSINYE"}
    if order_type not in valid_order_types:
        order_type = "ALL"
    if order_type != "ALL":
        unshipped_after_week = [
            row for row in unshipped_after_week
            if (row["order"].siparis_tipi or "").upper() == order_type
        ]

    paginator = Paginator(problems, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    unshipped_paginator = Paginator(unshipped_after_week, 50)
    unshipped_page_obj = unshipped_paginator.get_page(request.GET.get("unshipped_page"))

    section = (request.GET.get("section") or "problems").strip()
    if section not in {"problems", "unshipped"}:
        section = "problems"

    show_excluded = request.GET.get("excluded") == "1"
    excluded_type = "stage_problem" if section == "problems" else "unshipped_7d"
    excluded_rows = (
        ProductionStageControlExclusion.objects
        .filter(control_type=excluded_type)
        .select_related("order", "order__musteri", "excluded_by")
        .order_by("-excluded_at", "-id")
        if show_excluded
        else ProductionStageControlExclusion.objects.none()
    )

    return render(request, "core/production_stage_control.html", {
        "problems": page_obj,
        "problem_count": len(problems),
        "unshipped_orders": unshipped_page_obj,
        "unshipped_count": len(unshipped_after_week),
        "excluded_rows": excluded_rows,
        "excluded_count": ProductionStageControlExclusion.objects.filter(control_type=excluded_type).count(),
        "show_excluded": show_excluded,
        "section": section,
        "order_type": order_type,
    })
