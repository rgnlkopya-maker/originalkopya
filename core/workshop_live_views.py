"""Atölye canlı durum: existing open 'başladı' stage events and today's shipping plan.

This page is strictly read-only. A stage is open when its latest Başladı/Bitti
event is Başladı, regardless of which employee eventually pressed Bitti.
"""
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone

from app_settings.access import has_full_access
from planning.models import PlanningEntry, ShipmentPlan
from .models import OrderEvent
from .services.order_status import status_label, latest_status_event

LOCAL_STAGES = {
    "kesim_durum": "Kesim",
    "dikim_durum": "Dikim",
    "ust_etek_dikimi": "Üst Etek Dikimi",
    "susleme_durum": "Süsleme",
    "utu_durum": "Ütü",
}


@login_required
def workshop_live(request):
    if not has_full_access(request.user):
        return HttpResponseForbidden("Atölye canlı durum erişim yetkiniz bulunmuyor.")

    now = timezone.now()
    today = timezone.localdate()
    # Postgres DISTINCT ON selects the most recent start or finish per order/stage.
    # Queue, outsourcing, helping and unrelated events do not affect an open operation.
    recent_states = (
        OrderEvent.objects.filter(
            event_type="stage",
            stage__in=LOCAL_STAGES,
            value__in=("basladi", "bitti"),
            order__is_active=True,
        )
        .exclude(order__siparis_tipi="MALZEME")
        .select_related("order", "order__musteri")
        .order_by("order_id", "stage", "-timestamp", "-id")
        .distinct("order_id", "stage")
    )
    open_work = []
    for event in recent_states:
        if event.value != "basladi":
            continue
        order = event.order
        open_work.append({
            "order": order,
            "operation": status_label(event),
            "stage_name": LOCAL_STAGES[event.stage],
            "person": event.user or "—",
            "started": event.timestamp,
            "elapsed_minutes": max(0, int((now - event.timestamp).total_seconds() // 60)),
        })
    open_work.sort(key=lambda item: item["started"], reverse=True)

    # Mirror today's source column from the existing Shipment Plan and its notes.
    shipment_plans = list(
        ShipmentPlan.objects.filter(planned_date=today)
        .select_related("order", "order__musteri")
        .order_by("order__siparis_numarasi", "id")
    )
    shipments = [
        {
            "id": plan.id,
            "order": plan.order,
            "invoiced": plan.invoiced,
            "status": status_label(latest_status_event(plan.order)),
        }
        for plan in shipment_plans
    ]
    shipment_notes = list(
        PlanningEntry.objects.filter(section="sevkiyat", date=today).order_by("id")
    )
    return render(request, "core/workshop_live.html", {
        "open_work": open_work,
        "shipments": shipments,
        "shipment_notes": shipment_notes,
        "today": today,
        "updated_at": now,
        "open_count": len(open_work),
    })
