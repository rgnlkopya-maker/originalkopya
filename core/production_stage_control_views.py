from collections import defaultdict

from app_settings.access import data_scope_value
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from .models import Order, OrderEvent


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

    problems = []
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

        # Aynı eksikliği birden fazla kural yakalasa bile ekranda bir kez göster.
        reasons = list(dict.fromkeys(reasons))
        if not reasons:
            continue

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

    paginator = Paginator(problems, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "core/production_stage_control.html", {
        "problems": page_obj,
        "problem_count": len(problems),
    })
