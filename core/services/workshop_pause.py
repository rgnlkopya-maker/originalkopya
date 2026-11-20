"""Pause a worker's previously active production task when another task starts.

A pause is a real OrderEvent in the original worker's name, explicitly marked
as automatic. It is not a completion and never removes event history.
"""
from django.utils import timezone
from core.models import OrderEvent

TRACKED_STAGES = ("kesim_durum", "dikim_durum", "ust_etek_dikimi", "susleme_durum", "utu_durum")
CLOSING_VALUES = ("basladi", "bitti", "beklemede")


def pause_previous_work(*, user, incoming_order, incoming_stage, timestamp=None):
    """Pause the most recent open task of this worker, leaving historical records alone.

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
    candidates = [
        event for event in current_states
        if event.value == "basladi" and event.user == user.username
        and (event.order_id != incoming_order.id or event.stage != incoming_stage)
    ]
    if not candidates:
        return []
    # Legacy records can include many unclosed starts. Alter only the latest
    # active job rather than silently modifying every historical order.
    event = max(candidates, key=lambda entry: (entry.timestamp, entry.id))
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
    return [previous.id]
