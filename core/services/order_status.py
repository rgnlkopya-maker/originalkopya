from django.core.exceptions import FieldDoesNotExist
from django.db import models

from core.models import OrderEvent


FINANCIAL_STAGES = {
    "satis_fiyati",
    "ekstra_maliyet",
    "maliyet_override",
    "maliyet_uygulanan",
}

STATUS_LABELS = {
    ("kesim_durum", "basladi"): "Kesim Başladı",
    ("kesim_durum", "kismi_bitti"): "Kısmi Kesim Yapıldı",
    ("kesim_durum", "bitti"): "Kesildi",
    ("dikim_durum", "siraya_alindi"): "Dikim Sırasına Alındı",
    ("dikim_durum", "sıraya_alındı"): "Dikim Sırasına Alındı",
    ("dikim_durum", "basladi"): "Dikim Başladı",
    ("dikim_durum", "kismi_bitti"): "Kısmi Dikim Yapıldı",
    ("dikim_durum", "bitti"): "Dikildi",
    ("susleme_durum", "siraya_alindi"): "Süsleme Sırasına Alındı",
    ("susleme_durum", "sıraya_alındı"): "Süsleme Sırasına Alındı",
    ("susleme_durum", "basladi"): "Süsleme Başladı",
    ("susleme_durum", "kismi_bitti"): "Kısmi Süsleme Yapıldı",
    ("susleme_durum", "bitti"): "Süslendi",
    ("sevkiyat_durum", "gonderildi"): "Sevkiyat Gönderildi",
}


def latest_status_event(order):
    """Sipariş geçmişinde kalan en son üretim/sevkiyat hareketini döndürür."""
    return (
        OrderEvent.objects.filter(order=order)
        .exclude(event_type="order_update")
        .exclude(stage__in=FINANCIAL_STAGES)
        .order_by("-timestamp", "-id")
        .first()
    )


def status_label(event):
    if event is None:
        return "-"
    return STATUS_LABELS.get(
        (event.stage, event.value),
        f"{event.stage.replace('_durum', '').replace('_', ' ').title()} → "
        f"{event.value.replace('_', ' ').title()}",
    )


def sync_order_stage_from_events(order, stage):
    """Silinen bir hareketten sonra yalnızca ilgili aşamanın güncel değerini kurar."""
    try:
        field = order._meta.get_field(stage)
    except FieldDoesNotExist:
        return None

    if not isinstance(field, models.CharField):
        return None

    latest_value = (
        OrderEvent.objects.filter(
            order=order,
            event_type="stage",
            stage=stage,
        )
        .order_by("-timestamp", "-id")
        .values_list("value", flat=True)
        .first()
    )
    value = latest_value if latest_value is not None else field.get_default()
    setattr(order, stage, value)
    order.save(update_fields=[stage])
    return value
