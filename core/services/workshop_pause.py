"""Pause a worker's previously active production task when another task starts.

A pause is a real OrderEvent in the original worker's name, explicitly marked
as automatic. It is not a completion and never removes event history.
"""
from django.utils import timezone
from core.models import Order, OrderEvent

TRACKED_STAGES = ("kesim_durum", "dikim_durum", "ust_etek_dikimi", "susleme_durum", "utu_durum")
CLOSING_VALUES = ("basladi", "bitti", "beklemede")


def pause_previous_work(*, user, incoming_order, incoming_stage, timestamp=None):
    """Close prior open starts made by this worker, without touching other workers' jobs.

    Query the latest start/finish/pause per order+stage, then pause only if the
    latest open start was made by this exact logged-in employee. This respects a
    different employee pressing Bitti or restarting a stage.
    """
    timestamp = timestamp or timezone.now()
    current_states = (
        OrderEvent.objects.filter(
            event_type="stage", stage__in=TRACKED_STAGES, value__in=CLOSING_VALUES,
            order__is_active=True,
        )
        .select_related("order")
        .order_by("order_id", "stage", "-timestamp", "-id")
        .distinct("order_id", "stage")
    )
    paused = []
    for event in current_states:
        if event.value != "basladi" or event.user != user.username:
            continue
        if event.order_id == incoming_order.id and event.stage == incoming_stage:
            continue
        # Only one currently open task per worker, including existing stale starts.
        previous = event.order
        OrderEvent.objects.create(
            order=previous,
            user=user.username,
            gorev=event.gorev,
            stage=event.stage,
            value="beklemede",
            aciklama=f"Otomatik beklemeye alındı: {incoming_order.siparis_numarasi} numaralı siparişte yeni işe başlandı.",
            adet=previous.adet or 1,
            timestamp=timestamp,
            event_type="stage",
        )
        if event.stage in {"kesim_durum", "dikim_durum", "susleme_durum"}:
            setattr(previous, event.stage, "beklemede")
            previous.save(update_fields=[event.stage])
        paused.append(previous.id)
    return paused
