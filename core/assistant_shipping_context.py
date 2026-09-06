from datetime import timedelta

from django.utils import timezone

from planning.models import PlanningEntry, ShipmentPlan


MAX_ROWS = 80


def build_shipping_context():
    today = timezone.localdate()
    next_week_start = today + timedelta(days=(7 - today.weekday()))
    next_week_end = next_week_start + timedelta(days=6)
    horizon_end = today + timedelta(days=30)

    plans = (
        ShipmentPlan.objects
        .filter(planned_date__range=(today, horizon_end))
        .select_related("order", "order__musteri")
        .order_by("planned_date", "order__siparis_numarasi")[:MAX_ROWS]
    )
    notes = (
        PlanningEntry.objects
        .filter(section="sevkiyat", date__range=(today, horizon_end))
        .exclude(note="")
        .order_by("date")[:MAX_ROWS]
    )

    lines = [
        "MOLI SEVKIYAT PLANLAMA TAKVIMI (SALT OKUNUR):",
        f"Bugün: {today.isoformat()}",
        f"Önümüzdeki hafta: {next_week_start.isoformat()} - {next_week_end.isoformat()}",
        "ÖNEMLİ: Sevkiyat Planı, sipariş teslim tarihinden ayrı bir kaynaktır. Kullanıcı 'planlanan sevkiyat', 'sevkiyat takvimi', 'önümüzdeki hafta sevkiyat' gibi bir şey sorarsa aşağıdaki ShipmentPlan ve sevkiyat notlarını esas al. Teslim tarihiyle karıştırma.",
        "",
        "Siparişe bağlı sevkiyat planları (önümüzdeki 30 gün):",
    ]

    if plans:
        for plan in plans:
            order = plan.order
            customer = order.musteri.ad if order.musteri else "Stoğa Üretim"
            lines.append(
                f"- tarih={plan.planned_date.isoformat()} | sipariş={order.siparis_numarasi} | "
                f"müşteri={customer} | ürün={order.urun_kodu or '-'} | renk={order.renk or '-'} | "
                f"beden={order.beden or '-'} | adet={order.adet or 0}"
            )
    else:
        lines.append("- Kayıt yok")

    lines += ["", "Sevkiyat takvimine elle yazılan notlar (önümüzdeki 30 gün):"]
    if notes:
        for entry in notes:
            clean_note = (entry.note or "").replace("\n", " | ").strip()
            lines.append(f"- tarih={entry.date.isoformat()} | not={clean_note}")
    else:
        lines.append("- Not yok")

    next_week_plan_count = ShipmentPlan.objects.filter(
        planned_date__range=(next_week_start, next_week_end)
    ).count()
    next_week_notes = list(
        PlanningEntry.objects
        .filter(section="sevkiyat", date__range=(next_week_start, next_week_end))
        .exclude(note="")
        .values_list("date", "note")
    )
    lines += [
        "",
        f"ÖNÜMÜZDEKİ HAFTA ÖZETİ: siparişe bağlı plan={next_week_plan_count}, elle yazılmış sevkiyat notu={len(next_week_notes)}.",
    ]
    for note_date, note in next_week_notes:
        lines.append(f"- {note_date.isoformat()}: {(note or '').replace(chr(10), ' | ').strip()}")

    return "\n".join(lines)
