from datetime import timedelta, time
from decimal import Decimal

from django.db import migrations
from django.utils import timezone


def enrich_dashboard_demo(apps, schema_editor):
    Order = apps.get_model("core", "Order")
    OrderEvent = apps.get_model("core", "OrderEvent")

    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    while yesterday.weekday() >= 5:
        yesterday -= timedelta(days=1)

    tz = timezone.get_current_timezone()

    def at(day, hour, minute=0):
        return timezone.make_aware(timezone.datetime.combine(day, time(hour, minute)), tz)

    orders = list(
        Order.objects.filter(siparis_numarasi__startswith="DMO", is_active=True)
        .exclude(siparis_tipi="MALZEME")
        .order_by("id")[:36]
    )
    if len(orders) < 18:
        return

    # Bu migrasyon yeniden calistirilsa bile ayni demo hareketlerini cogaltma.
    OrderEvent.objects.filter(user="Eylus Demo", aciklama__startswith="[EYLUS-DASHBOARD]").delete()

    today_plan = [
        ("kesim_durum", "bitti", "kesim", 0, 8, 42),
        ("kesim_durum", "bitti", "kesim", 1, 9, 5),
        ("dikim_durum", "bitti", "dikim", 2, 9, 28),
        ("dikim_durum", "bitti", "dikim", 3, 10, 12),
        ("dikim_durum", "bitti", "dikim", 4, 10, 46),
        ("susleme_durum", "bitti", "susleme", 5, 11, 15),
        ("susleme_durum", "bitti", "susleme", 6, 11, 52),
        ("hazir_durum", "bitti", "hazir", 7, 12, 20),
        ("hazir_durum", "bitti", "hazir", 8, 13, 5),
        ("hazir_durum", "bitti", "hazir", 9, 13, 38),
    ]

    for stage, value, role, idx, hour, minute in today_plan:
        order = orders[idx]
        setattr(order, stage, value)
        order.save(update_fields=[stage, "last_updated"])
        OrderEvent.objects.create(
            order=order, user="Eylus Demo", gorev=role, stage=stage, value=value,
            adet=order.adet or 1, event_type="stage", timestamp=at(today, hour, minute),
            aciklama="[EYLUS-DASHBOARD] Bugun gerceklesen demo uretim hareketi",
        )

    yesterday_plan = [
        ("kesim_durum", "bitti", "kesim", 10, 9, 10),
        ("kesim_durum", "bitti", "kesim", 11, 9, 36),
        ("dikim_durum", "bitti", "dikim", 12, 10, 20),
        ("dikim_durum", "bitti", "dikim", 13, 11, 5),
        ("susleme_durum", "bitti", "susleme", 14, 12, 15),
        ("susleme_durum", "bitti", "susleme", 15, 13, 0),
        ("hazir_durum", "bitti", "hazir", 16, 14, 10),
        ("hazir_durum", "bitti", "hazir", 17, 15, 0),
    ]

    for stage, value, role, idx, hour, minute in yesterday_plan:
        order = orders[idx]
        setattr(order, stage, value)
        order.save(update_fields=[stage, "last_updated"])
        OrderEvent.objects.create(
            order=order, user="Eylus Demo", gorev=role, stage=stage, value=value,
            adet=order.adet or 1, event_type="stage", timestamp=at(yesterday, hour, minute),
            aciklama="[EYLUS-DASHBOARD] Dun gerceklesen demo uretim hareketi",
        )

    # Dunun sevkiyatlari: gercek siparis + satis/maliyet snapshot'i + sevkiyat eventi.
    shipped = orders[18:23]
    prices = [
        (Decimal("16800.00"), Decimal("10150.00")),
        (Decimal("14250.00"), Decimal("8920.00")),
        (Decimal("21900.00"), Decimal("13750.00")),
        (Decimal("12500.00"), Decimal("7640.00")),
        (Decimal("18650.00"), Decimal("11280.00")),
    ]
    for offset, (order, values) in enumerate(zip(shipped, prices)):
        sale, cost = values
        shipped_at = at(yesterday, 15 + (offset // 2), 10 + (offset * 7) % 45)
        order.satis_fiyati = sale
        order.para_birimi = "TRY"
        order.maliyet_uygulanan = cost
        order.maliyet_para_birimi = "TRY"
        order.maliyet_override = None
        order.ekstra_maliyet = Decimal("0")
        order.sevkiyat_durum = "gonderildi"
        order.sevkiyat_yapan = "Eylus Demo"
        order.sevkiyat_tarihi = shipped_at
        order.save(update_fields=[
            "satis_fiyati", "para_birimi", "maliyet_uygulanan", "maliyet_para_birimi",
            "maliyet_override", "ekstra_maliyet", "sevkiyat_durum",
            "sevkiyat_yapan", "sevkiyat_tarihi", "last_updated",
        ])
        OrderEvent.objects.create(
            order=order, user="Eylus Demo", gorev="sevkiyat",
            stage="sevkiyat_durum", value="gonderildi", adet=order.adet or 1,
            event_type="stage", timestamp=shipped_at,
            aciklama="[EYLUS-DASHBOARD] Dun sevk edilen demo siparisi",
        )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0080_realistic_eylus_demo_leave_history"),
    ]

    operations = [
        migrations.RunPython(enrich_dashboard_demo, migrations.RunPython.noop),
    ]
