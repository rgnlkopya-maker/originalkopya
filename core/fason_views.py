from collections import defaultdict, deque

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Fasoncu, OrderEvent

FASON_STAGES = {
    "dikim_fason_durumu": "Dikim",
    "susleme_fason_durumu": "Süsleme",
}


def _fason_events():
    return (
        OrderEvent.objects
        .select_related("order", "order__musteri", "fasoncu")
        .filter(
            stage__in=FASON_STAGES.keys(),
            fasoncu__isnull=False,
            value__in=["verildi", "alindi"],
        )
        .order_by("timestamp", "id")
    )


@login_required
def fasoncu_raporu(request):
    fasoncular = Fasoncu.objects.all().order_by("ad")
    all_events = _fason_events()

    grouped = defaultdict(list)
    for event in all_events:
        grouped[(event.fasoncu_id, event.order_id, event.stage)].append(event)

    open_jobs = []
    today = timezone.localdate()
    for (fasoncu_id, order_id, stage), group_events in grouped.items():
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

    return render(request, "reports/fasoncu_raporu.html", {
        "fasoncular": fasoncular,
        "open_jobs": open_jobs,
    })


@login_required
def fasoncu_detay(request, fasoncu_id):
    fasoncu = get_object_or_404(Fasoncu, pk=fasoncu_id)
    events = list(_fason_events().filter(fasoncu=fasoncu))

    # Her 'verildi' hareketini ayrı bir iş satırı olarak tutuyoruz.
    # 'alindi' hareketleri aynı sipariş + aşama içinde FIFO ile gönderimlere bağlanır.
    queues = defaultdict(deque)
    rows = []

    for event in events:
        key = (event.order_id, event.stage)
        qty = event.adet or 1

        if event.value == "verildi":
            row = {
                "order": event.order,
                "islem": FASON_STAGES.get(event.stage, "Fason"),
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

    def text(v):
        return (v or "").casefold()

    sorters = {
        "verilis": lambda r: r["verilis_tarihi"],
        "siparis_tipi": lambda r: text(r["order"].get_siparis_tipi_display() if r["order"].siparis_tipi else ""),
        "musteri": lambda r: text(r["order"].musteri.ad if r["order"].musteri else ""),
        "urun": lambda r: text(r["order"].urun_kodu),
        "renk": lambda r: text(r["order"].renk),
        "beden": lambda r: text(r["order"].beden),
        "islem": lambda r: text(r["islem"]),
        "adet": lambda r: r["adet"],
        "donus": lambda r: r["donus_tarihi"] or timezone.make_aware(timezone.datetime.min),
    }
    sorter = sorters.get(sort_key, sorters["verilis"])
    rows.sort(key=sorter, reverse=reverse)

    return render(request, "reports/fasoncu_detay.html", {
        "fasoncu": fasoncu,
        "rows": rows,
        "sort_key": sort_key,
        "sort_dir": sort_dir,
        "total_jobs": len(rows),
        "open_jobs": sum(1 for row in rows if not row["donus_tarihi"]),
    })
