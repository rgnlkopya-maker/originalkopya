from collections import defaultdict

from app_settings.access import data_scope_value
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import timedelta

from .models import ConsignmentMovement, ConsignmentStock, Order, OrderEvent, ProductionStageControlExclusion


STAGES = {
    "kesim": ("kesim_durum", "Kesim"),
    "dikim": ("dikim_durum", "Dikim"),
    "susleme": ("susleme_durum", "Süsleme"),
}

REQUIRED_VALUES = ("basladi", "bitti")



def _manager_event_names():
    """Usernames/full names saved as strings in OrderEvent.user for patron/mudur."""
    User = get_user_model()
    managers = (
        User.objects.filter(groups__name__in=("patron", "mudur"))
        | User.objects.filter(is_superuser=True)
    ).distinct().values("username", "first_name", "last_name")
    names = set()
    for user in managers:
        username = (user["username"] or "").strip()
        full_name = " ".join(part for part in ((user["first_name"] or "").strip(), (user["last_name"] or "").strip()) if part)
        for value in (username, full_name):
            if value:
                names.add(" ".join(value.casefold().split()))
    return names


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
            "beden", "adet", "siparis_tipi", "is_active", "sevkiyat_durum"
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
        "konsinye_durum",
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

    # A consigned item is already with the customer; consumed consignment stock
    # has fulfilled another order. Count both so partially consigned orders
    # remain visible until their entire quantity is accounted for.
    consignment_out = {
        row["source_order_id"]: row["total"]
        for row in (
            ConsignmentStock.objects.filter(
                source_order_id__in=order_ids, quantity_remaining__gt=0
            )
            .values("source_order_id")
            .annotate(total=Sum("quantity_remaining"))
        )
    }
    consignment_used = {
        row["stock__source_order_id"]: row["total"]
        for row in (
            ConsignmentMovement.objects.filter(
                stock__source_order_id__in=order_ids,
                movement_type="USE",
            )
            .values("stock__source_order_id")
            .annotate(total=Sum("quantity"))
        )
    }

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
        # A completed consignment is not a stalled production order.
        # Returned stock decreases the active balance, reopening monitoring
        # for the missing quantity after the most recent consignment movement.
        accounted_qty = consignment_out.get(order.id, 0) + consignment_used.get(order.id, 0)
        fully_consigned = accounted_qty >= (order.adet or 1)
        temporarily_hidden = (order.id, "unshipped_3d_temp") in exclusions
        permanently_hidden = (order.id, "unshipped_7d") in exclusions
        if not shipped and not fully_consigned and not temporarily_hidden and not permanently_hidden:
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
    personnel_entries = defaultdict(list)
    manager_names = _manager_event_names()
    unshipped_after_week = get_unshipped_inactive_orders(request.user)
    for order in orders:
        events = events_by_order.get(order.id, [])
        if not events:
            continue

        reasons = []
        attributions = []

        # Yalnizca kullanilmis asama butonlarinin esini kontrol et.
        # "Bitti" varsa "Basladi" her zaman beklenir.
        # "Basladi" varsa "Bitti" ancak sonraki asamaya gecilince beklenir.
        # Iki butona da basilmamissa o asama icin problem uretilmez.
        later_stages = {
            "kesim": {
                "dikim_durum", "dikim_fason_durumu", "nakis_durumu",
                "susleme_durum", "susleme_fason_durumu", "hazir_durum",
                "sevkiyat_durum",
            },
            "dikim": {
                "susleme_durum", "susleme_fason_durumu", "hazir_durum",
                "sevkiyat_durum",
            },
            "susleme": {"hazir_durum", "sevkiyat_durum"},
        }
        for stage_key, (stage_name, label) in STAGES.items():
            stage_events = [event for event in events if event.stage == stage_name]
            started = any(event.value == "basladi" for event in stage_events)
            finished = any(event.value == "bitti" for event in stage_events)
            if finished and not started:
                reason = f"{label} Başladı"
                reasons.append(reason)
                # The person who explicitly clicked Finished is accountable
                # for the absent matching Started event, not the last editor.
                actor_event = next(event for event in reversed(stage_events) if event.value == "bitti")
                attributions.append({
                    "reason": reason, "actor": (actor_event.user or "").strip() or "Bilinmeyen personel",
                    "trigger": f"{label} Bitti", "timestamp": actor_event.timestamp,
                })
            if started and not finished:
                first_start = next(
                    event for event in stage_events if event.value == "basladi"
                )
                next_event = next((
                    event for event in events
                    if event.stage in later_stages[stage_key]
                    and (event.timestamp, event.id) > (first_start.timestamp, first_start.id)
                ), None)
                if next_event:
                    reason = f"{label} Bitti"
                    reasons.append(reason)
                    # Süsleme Bitti eksikse sorumlu Süsleme Başladı işlemini yapan kişidir.
                    # Diğer aşamaların mevcut atıf kuralını koru.
                    responsible_event = first_start if stage_key == "susleme" else next_event
                    attributions.append({
                        "reason": reason,
                        "actor": (responsible_event.user or "").strip() or "Bilinmeyen personel",
                        "trigger": f"{label} Başladı" if stage_key == "susleme" else "Sonraki aşamaya geçiş",
                        "timestamp": responsible_event.timestamp,
                    })

        # Güncel sevkiyat durumunu son sevkiyat hareketinden belirle.
        shipment_events = [event for event in events if event.stage == "sevkiyat_durum"]
        shipped = (
            shipment_events[-1].value == "gonderildi"
            if shipment_events
            else order.sevkiyat_durum == "gonderildi"
        )

        # Patron/mudur kaynakli islemleri HATA listelerine dahil etme.
        # Siparisteki diger personel sorunlari gorunmeye devam eder.
        attributions = [
            item for item in attributions
            if " ".join(item["actor"].casefold().split()) not in manager_names
        ]
        reasons = list(dict.fromkeys(item["reason"] for item in attributions))
        if reasons and (order.id, "stage_problem") not in exclusions:
            last_event = events[-1]
            problems.append({
                "order": order,
                "reasons": reasons,
                "attributions": attributions,
                "last_event": last_event,
                "shipped": shipped,
            })

    # Group each missing action separately: one order may appear under
    # different personnel when two different transitions are responsible.
    for row in problems:
        for attribution in row["attributions"]:
            personnel_entries[attribution["actor"]].append({
                "order": row["order"], "shipped": row["shipped"],
                **attribution,
            })

    personnel_groups = [
        {"name": name, "count": len(entries),
         "orders_count": len({entry["order"].id for entry in entries})}
        for name, entries in personnel_entries.items()
    ]
    personnel_groups.sort(key=lambda item: (-item["count"], item["name"].casefold()))
    view_mode = (request.GET.get("view") or "list").strip()
    if view_mode not in {"list", "personnel"}:
        view_mode = "list"
    selected_person = (request.GET.get("person") or "").strip()
    # Only allow exact names observed in the scoped, non-excluded issues.
    if selected_person not in personnel_entries:
        selected_person = ""
    person_issues = personnel_entries.get(selected_person, []) if selected_person else []
    person_issues.sort(key=lambda item: item["timestamp"], reverse=True)

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
        "view_mode": view_mode,
        "personnel_groups": personnel_groups,
        "selected_person": selected_person,
        "person_issues": person_issues,
        "person_issue_count": len(person_issues),
        "problem_count": len(problems),
        "unshipped_orders": unshipped_page_obj,
        "unshipped_count": len(unshipped_after_week),
        "excluded_rows": excluded_rows,
        "excluded_count": ProductionStageControlExclusion.objects.filter(control_type=excluded_type).count(),
        "show_excluded": show_excluded,
        "section": section,
        "order_type": order_type,
    })
