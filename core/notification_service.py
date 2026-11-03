"""Central in-app notification publisher (phase one).

Order updates use this service; other notification flows will be migrated
separately without altering their existing behaviour.
"""
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Notification

ORDER_FIELD_LABELS = {
    "musteri": "Müşteri",
    "siparis_tipi": "Sipariş Tipi",
    "urun_kodu": "Ürün Kodu",
    "renk": "Renk",
    "beden": "Beden",
    "adet": "Adet",
    "aciklama": "Açıklama",
    "musteri_referans": "Müşteri Ref",
    "teslim_tarihi": "Teslim Tarihi",
    "satis_fiyati": "Satış Fiyatı",
    "vat_rate": "KDV Oranı",
    "ekstra_maliyet": "Ekstra Maliyet",
    "maliyet_override": "Manuel Maliyet",
}


def management_recipients():
    """Active patron/mudur users and superusers, without duplication."""
    return get_user_model().objects.filter(is_active=True).filter(
        Q(is_superuser=True) | Q(groups__name__in=("patron", "mudur"))
    ).distinct()


def publish_order_update(*, order, changed_fields, actor):
    """Persist one manager-only in-app notice per order edit.

    Browser Push is deliberately unchanged: legacy edits only wrote notices.
    """
    if not changed_fields:
        return 0
    labels = [ORDER_FIELD_LABELS.get(field, field) for field in changed_fields]
    username = actor.username if actor else "Sistem"
    title = f"{order.siparis_numarasi} güncellendi"
    message = f"Değişen alanlar: {', '.join(labels)}. Güncelleyen: {username}"
    recipients = list(management_recipients().values_list("pk", flat=True))
    if not recipients:
        return 0
    from .notification_preferences import event_delivery, settings_for_recipients
    choices = settings_for_recipients(recipients)
    enabled = [uid for uid in recipients
               if event_delivery(choices.get(uid, {}), "order_update")[0]]
    if enabled:
        Notification.objects.bulk_create([
            Notification(user_id=uid, order=order, title=title, message=message)
            for uid in enabled
        ])
    return len(enabled)
