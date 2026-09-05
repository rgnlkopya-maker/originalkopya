from collections import defaultdict, deque
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from .models import Fasoncu, OrderEvent

FASON_STAGES = {
    "dikim_fason_durumu": "Dikim",
    "susleme_fason_durumu": "Süsleme",
}


@login_required
def fasoncu_raporu(request):
    fasoncular = Fasoncu.objects.all().order_by("ad")
    fasoncu_id = (request.GET.get("fasoncu") or "").strip()
    t1 = (request.GET.get("t1") or "").strip()
    t2 = (request.GET.get("t2") or "").strip()

    all_events = (
        OrderEvent.objects
        .select_related("order", "order__musteri", "fasoncu")
        .filter(stage__in=FASON_STAGES.keys(), fasoncu__isnull=False, value__in=["verildi", "alindi"])
        .order_by("timestamp", "id")
    )

    events = all_events
    if fasoncu_id:
        events = events.filter(fasoncu_id=fasoncu_id)
    if t1:
        events = events.filter(timestamp__date__gte=t1)
    if t2:
        events = events.filter(timestamp__date__lte=t2)

    # Seçilen dönemin hareket tablosu.
    raporlar = []
    period_given = 0
    period_received = 0
    for event in events.order_by("-timestamp", "-id"):
        qty = event.adet or 1
        if event.value == "verildi":
            period_given += qty
        else:
            period_received += qty
        raporlar.append({
            "event": event,
            "order": event.order,
            "fasoncu": event.fasoncu,
            "islem": FASON_STAGES.get(event.stage, "Fason"),
            "durum": "Fasona Verildi" if event.value == "verildi" else "Fasondan Alındı",
            "adet": qty,
            "tarih": event.timestamp,
            "personel": event.user,
            "aciklama": event.aciklama or "",
        })

    # Güncel dışarıdaki adet hesabı tarih filtresinden bağımsızdır; bugün gerçekte fasoncuda ne var onu gösterir.
    grouped = defaultdict(list)
    vendor_totals = defaultdict(lambda: {"given": 0, "received": 0, "outstanding": 0})
    for event in all_events:
        qty = event.adet or 1
        key = (event.fasoncu_id, event.order_id, event.stage)
        grouped[key].append(event)
        if event.value == "verildi":
            vendor_totals[event.fasoncu_id]["given"] += qty
        else:
            vendor_totals[event.fasoncu_id]["received"] += qty

    open_jobs = []
    today = timezone.localdate()
    for (fasoncu_id_key, order_id, stage), group_events in grouped.items():
        queue = deque()
        total_given = 0
        total_received = 0
        for event in group_events:
            qty = event.adet or 1
            if event.value == "verildi":
                total_given += qty
                queue.append([qty, event.timestamp])
            else:
                total_received += qty
                remaining_to_match = qty
                while remaining_to_match > 0 and queue:
                    batch_qty, batch_time = queue[0]
                    consume = min(batch_qty, remaining_to_match)
                    batch_qty -= consume
                    remaining_to_match -= consume
                    if batch_qty <= 0:
                        queue.popleft()
                    else:
                        queue[0][0] = batch_qty

        outstanding = max(0, total_given - total_received)
        if outstanding <= 0:
            continue

        first_event = group_events[0]
        oldest_time = queue[0][1] if queue else first_event.timestamp
        oldest_date = timezone.localtime(oldest_time).date() if timezone.is_aware(oldest_time) else oldest_time.date()
        days_out = max(0, (today - oldest_date).days)
        vendor_totals[fasoncu_id_key]["outstanding"] += outstanding

        open_jobs.append({
            "fasoncu": first_event.fasoncu,
            "order": first_event.order,
            "islem": FASON_STAGES.get(stage, "Fason"),
            "verilen": total_given,
            "alinan": total_received,
            "kalan": outstanding,
            "verilis_tarihi": oldest_time,
            "gun": days_out,
        })

    open_jobs.sort(key=lambda row: (-row["gun"], row["fasoncu"].ad, row["order"].id))

    vendor_cards = []
    for fasoncu in fasoncular:
        totals = vendor_totals[fasoncu.id]
        vendor_cards.append({
            "fasoncu": fasoncu,
            "verilen": totals["given"],
            "alinan": totals["received"],
            "disarida": totals["outstanding"],
        })

    selected_open_jobs = open_jobs
    if fasoncu_id:
        try:
            selected_id = int(fasoncu_id)
            selected_open_jobs = [row for row in open_jobs if row["fasoncu"].id == selected_id]
        except ValueError:
            selected_open_jobs = open_jobs

    return render(request, "reports/fasoncu_raporu.html", {
        "fasoncular": fasoncular,
        "raporlar": raporlar,
        "vendor_cards": vendor_cards,
        "open_jobs": selected_open_jobs,
        "period_given": period_given,
        "period_received": period_received,
        "period_net": max(0, period_given - period_received),
        "total_outstanding": sum(item["outstanding"] for item in vendor_totals.values()),
    })
