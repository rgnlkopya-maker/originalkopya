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


@login_required
@require_POST
def exclude_from_production_stage_control(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    control_type = (request.POST.get("control_type") or "").strip()
    valid_types = {value for value, _label in ProductionStageControlExclusion.CONTROL_TYPES}
    if control_type not in valid_types:
        return redirect("production_stage_control")

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
            "beden", "siparis_tipi", "is_active"
        )
        .order_by("-id")
    )
    if data_scope_value(request.user, "orders") == "active_only":
        orders = orders.filter(is_active=True)

    order_ids = list(orders.values_list("id", flat=True))
    events_by_order = defaultdict(list)
    relevant_stages = {
        "kesim_durum", "dikim_durum", "dikim_fason_durumu",
        "susleme_durum", "susleme_fason_durumu", "hazir_durum",
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

    exclusions = {
        (row.order_id, row.control_type)
        for row in ProductionStageControlExclusion.objects.all().only("order_id", "control_type")
    }

    problems = []
    unshipped_after_week = []
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

        # Sevk gerçekleştiyse temel üretim zincirinin tamamını kontrol et.
        shipped = any(
            event.stage == "sevkiyat_durum" and event.value == "gonderildi"
            for event in events
        )
        if shipped:
            for stage_name, label in STAGES.values():
                reasons.extend(_missing_stage_steps(events, stage_name, label))

        # Son gerçek üretim hareketinden itibaren 3 gün boyunca sevkiyat yoksa
        # ayrı kontrol listesine al. Fiyat/açıklama gibi order_update kayıtları
        # üretim sayacını sıfırlamaz.
        production_stage_names = {
            "malzeme_durum",
            "kesim_durum",
            "dikim_durum",
            "dikim_fason_durumu",
            "nakis_durum",
            "susleme_durum",
            "susleme_fason_durumu",
            "hazir_durum",
            "uretim_aktarimi",
            "uretim_aktarimı",
        }
        production_events = [
            event for event in events
            if event.event_type == "stage" and event.stage in production_stage_names
        ]
        if production_events and not shipped:
            last_production_event = production_events[-1]
            age = timezone.now() - last_production_event.timestamp
            if age >= timedelta(days=3) and (order.id, "unshipped_7d") not in exclusions:
                unshipped_after_week.append({
                    "order": order,
                    "first_event": production_events[0],
                    "last_event": last_production_event,
                    "days_open": age.days,
                })

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

    unshipped_after_week.sort(
        key=lambda row: (-row["days_open"], row["first_event"].timestamp)
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
