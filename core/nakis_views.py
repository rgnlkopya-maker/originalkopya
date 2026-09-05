from collections import defaultdict, deque
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Nakisci, OrderEvent

NAKIS_STAGE = "nakis_durum"


def _nakis_events():
    return (
        OrderEvent.objects
        .select_related("order", "order__musteri", "nakisci")
        .filter(
            stage=NAKIS_STAGE,
            nakisci__isnull=False,
            value__in=["verildi", "alindi"],
        )
        .order_by("timestamp", "id")
    )


@login_required
def nakisci_raporu(request):
    nakiscilar = Nakisci.objects.all().order_by("ad")
    all_events = _nakis_events()

    grouped = defaultdict(list)
    for event in all_events:
        grouped[(event.nakisci_id, event.order_id)].append(event)

    open_jobs = []
    today = timezone.localdate()

    for (nakisci_id, order_id), group_events in grouped.items():
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
                to_match = qty
                while to_match > 0 and queue:
                    batch_qty, batch_time = queue[0]
                    consume = min(batch_qty, to_match)
                    batch_qty -= consume
                    to_match -= consume
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

        open_jobs.append({
            "nakisci": first_event.nakisci,
            "order": first_event.order,
            "verilen": total_given,
            "alinan": total_received,
            "kalan": outstanding,
            "verilis_tarihi": oldest_time,
            "gun": days_out,
        })

    open_jobs.sort(key=lambda row: (-row["gun"], row["nakisci"].ad, row["order"].id))

    return render(request, "reports/nakisci_raporu.html", {
        "nakiscilar": nakiscilar,
        "open_jobs": open_jobs,
    })


@login_required
def nakisci_detay(request, nakisci_id):
    nakisci = get_object_or_404(Nakisci, pk=nakisci_id)
    events = list(_nakis_events().filter(nakisci=nakisci))

    queues = defaultdict(deque)
    rows = []

    for event in events:
        key = event.order_id
        qty = event.adet or 1

        if event.value == "verildi":
            row = {
                "order": event.order,
                "adet": qty,
                "verilis_tarihi": event.timestamp,
                "donus_tarihi": None,
                "remaining": qty,
            }
            rows.append(row)
            queues[key].append(row)
            continue

        to_match = qty
        while to_match > 0 and queues[key]:
            row = queues[key][0]
            consume = min(row["remaining"], to_match)
            row["remaining"] -= consume
            to_match -= consume
            if row["remaining"] <= 0:
                row["donus_tarihi"] = event.timestamp
                queues[key].popleft()

    sort_key = (request.GET.get("sort") or "verilis").strip()
    sort_dir = (request.GET.get("dir") or "desc").strip()
    reverse = sort_dir == "desc"

    def text(value):
        return (value or "").casefold()

    min_dt = timezone.make_aware(datetime.min.replace(year=1970))
    sorters = {
        "verilis": lambda r: r["verilis_tarihi"],
        "siparis_tipi": lambda r: text(r["order"].get_siparis_tipi_display() if r["order"].siparis_tipi else ""),
        "musteri": lambda r: text(r["order"].musteri.ad if r["order"].musteri else ""),
        "urun": lambda r: text(r["order"].urun_kodu),
        "renk": lambda r: text(r["order"].renk),
        "beden": lambda r: text(r["order"].beden),
        "adet": lambda r: r["adet"],
        "donus": lambda r: r["donus_tarihi"] or min_dt,
    }
    rows.sort(key=sorters.get(sort_key, sorters["verilis"]), reverse=reverse)

    return render(request, "reports/nakisci_detay.html", {
        "nakisci": nakisci,
        "rows": rows,
        "sort_key": sort_key,
        "sort_dir": sort_dir,
        "total_jobs": len(rows),
        "open_jobs": sum(1 for row in rows if not row["donus_tarihi"]),
    })
