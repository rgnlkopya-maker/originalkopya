"""Atölye canlı durum: existing open 'başladı' stage events and today's shipping plan.

This page is strictly read-only. A stage is open when its latest Başladı/Bitti
event is Başladı, regardless of which employee eventually pressed Bitti.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.db.models import Count, Max
from django.contrib.auth import get_user_model
from datetime import datetime
from attendance.models import AttendanceRecord, WorkplaceSettings
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from app_settings.access import has_full_access
from planning.models import PlanningEntry, ShipmentPlan
from .models import OrderEvent, ProductionStageControlExclusion
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
    # One hidden entry per exact "Başladı" event. A later start is visible again.
    active_events = list(recent_states)
    excluded = set(
        ProductionStageControlExclusion.objects.filter(
            order_id__in=[event.order_id for event in active_events],
            control_type__startswith="workshop_",
        ).values_list("order_id", "control_type")
    )
    open_work = []
    for event in active_events:
        if event.value != "basladi" or (event.order_id, f"workshop_{event.id}") in excluded:
            continue
        order = event.order
        open_work.append({
            "event_id": event.id,
            "order": order,
            "operation": status_label(event),
            "stage_name": LOCAL_STAGES[event.stage],
            "person": event.user or "—",
            "started": event.timestamp,
            "elapsed_minutes": max(0, int((now - event.timestamp).total_seconds() // 60)),
        })

    # Attendance limits open durations to recorded work periods, never nights.
    # OrderEvent.user is free text, not a user FK.
    name_to_id, ambiguous = {}, set()
    for employee in get_user_model().objects.filter(is_active=True).only("id", "username", "first_name", "last_name"):
        for alias in {(employee.username or "").strip().casefold(), (employee.get_full_name() or "").strip().casefold()} - {""}:
            if alias in name_to_id and name_to_id[alias] != employee.pk:
                ambiguous.add(alias)
            else:
                name_to_id[alias] = employee.pk
    for alias in ambiguous:
        name_to_id.pop(alias, None)
    for row in open_work:
        row["employee_id"] = name_to_id.get((row["person"] or "").strip().casefold())
        row["elapsed_minutes"] = None
        row["work_sessions"] = []
    employee_ids = {row["employee_id"] for row in open_work if row["employee_id"]}
    if employee_ids:
        earliest = min(timezone.localtime(row["started"]).date() for row in open_work if row["employee_id"])
        records = AttendanceRecord.objects.filter(
            user_id__in=employee_ids, work_date__gte=earliest, work_date__lte=today,
            status="worked", check_in__isnull=False,
        ).order_by("work_date")
        attendance_by_user = {}
        for record in records:
            attendance_by_user.setdefault(record.user_id, []).append(record)
        settings = WorkplaceSettings.get_solo()
        for row in open_work:
            if not row["employee_id"]:
                continue
            intervals = []
            for record in attendance_by_user.get(row["employee_id"], []):
                start = max(row["started"], record.check_in)
                if record.check_out:
                    finish = record.check_out
                elif record.work_date == today:
                    finish = now
                else:
                    # Missing historical checkout is uncertain; cap at scheduled end.
                    finish = timezone.make_aware(
                        datetime.combine(record.work_date, settings.work_end),
                        timezone.get_current_timezone()
                    )
                finish = min(finish, now)
                if finish <= start:
                    continue
                intervals.append({
                    "start": start.isoformat(),
                    "end": finish.isoformat() if record.check_out or record.work_date != today else None,
                })
            row["work_sessions"] = intervals
            if not intervals:
                continue
            total_seconds = 0
            for segment in intervals:
                begin = datetime.fromisoformat(segment["start"])
                finish = datetime.fromisoformat(segment["end"]) if segment["end"] else now
                total_seconds += max(0, (finish - begin).total_seconds())
            row["elapsed_minutes"] = int(total_seconds // 60)

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


@login_required
@require_POST
def workshop_live_hide(request, event_id):
    """Only hide this exact active work row; never mutate production history."""
    if not has_full_access(request.user):
        return HttpResponseForbidden("Bu işlemi yapma yetkiniz yok.")
    event = get_object_or_404(
        OrderEvent,
        pk=event_id,
        event_type="stage",
        stage__in=LOCAL_STAGES,
        value="basladi",
        order__is_active=True,
    )
    # Confirm this row is still the latest start/finish for the order and stage.
    latest = (OrderEvent.objects.filter(
        order_id=event.order_id, stage=event.stage,
        event_type="stage", value__in=("basladi", "bitti"),
    ).order_by("-timestamp", "-id").values_list("id", flat=True).first())
    if latest != event.pk:
        return JsonResponse({"ok": False, "message": "Bu işlem artık açık değil. Sayfayı yenileyin."}, status=409)
    ProductionStageControlExclusion.objects.get_or_create(
        order_id=event.order_id,
        control_type=f"workshop_{event.pk}",
        defaults={"excluded_by": request.user},
    )
    return JsonResponse({"ok": True})


@login_required
def workshop_live_version(request):
    """Lightweight 3-second TV poll; full HTML fetched only after a data change."""
    if not has_full_access(request.user):
        return HttpResponseForbidden("Atölye canlı durum erişim yetkiniz bulunmuyor.")
    today = timezone.localdate()
    stage = OrderEvent.objects.aggregate(last_id=Max("id"))
    exclusions = ProductionStageControlExclusion.objects.aggregate(
        count=Count("id"), last_id=Max("id")
    )
    plans = ShipmentPlan.objects.filter(planned_date=today).aggregate(
        count=Count("id"), last_id=Max("id"), last_update=Max("updated_at")
    )
    notes = PlanningEntry.objects.filter(section="sevkiyat", date=today).aggregate(
        count=Count("id"), last_id=Max("id"), last_update=Max("updated_at")
    )
    attendance = AttendanceRecord.objects.aggregate(last_update=Max("updated_at"))
    # New events, manager exclusions, plan edits and date rollover change the version.
    key = "|".join(str(value or "") for value in (
        today.isoformat(), stage["last_id"],
        exclusions["count"], exclusions["last_id"],
        plans["count"], plans["last_id"], plans["last_update"],
        notes["count"], notes["last_id"], notes["last_update"],
        attendance["last_update"],
    ))
    response = JsonResponse({"version": key})
    response["Cache-Control"] = "no-store"
    return response
