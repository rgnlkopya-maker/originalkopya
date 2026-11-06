"""Notification preference rules shared by the management center and publishers.

Critical events cannot be silenced in the in-app inbox. Push is optional on
each device/account and remains subject to browser permission.
"""
from .models import NotificationPreference

EVENTS = (
    ("uninvoiced_shipment", "Faturaya aktarılmayan sevkiyat", False, True),
    ("invoice_failure", "Fatura aktarım hatası", True, True),
    ("material_missing", "Malzeme eksikliği", False, True),
    ("flagged_stage", "Bayraklı sipariş üretim hareketi", False, True),
    ("backup_failed", "Otomatik yedekleme hatası", True, True),
    ("security_lock", "Giriş güvenliği uyarısı", True, True),
    ("tomorrow_shipping", "Yarın teslim edilecek siparişler", False, True),
    ("stalled_production", "Üretim 3 gün hareketsiz", False, True),
    ("payable_instruments", "Çek/senet vadesine 15 gün kaldı", True, True),
)
EVENTS_BY_KEY = {key: {"title": name, "critical": critical, "push_default": push}
                 for key, name, critical, push in EVENTS}
EVENT_TITLE_KEYS = {
    "Faturaya Aktarılmayan Yeni Sevkiyat": "uninvoiced_shipment",
    "Fatura Aktarım Hatası": "invoice_failure",
    "Malzeme Eksikliği": "material_missing",
    "Bayraklı Siparişte Üretim Hareketi": "flagged_stage",
    "Otomatik Yedekleme Başarısız": "backup_failed",
    "Güvenlik Uyarısı": "security_lock",
    "Yarın Teslim Edilecek Siparişler": "tomorrow_shipping",
    "Üretim Aşaması Takıldı": "stalled_production",
    "Çek/Senet Vadesine 15 Gün Kaldı": "payable_instruments",
}


def event_delivery(settings, event_key):
    """Return (save_in_app, send_push), honoring mandatory critical inbox."""
    event = EVENTS_BY_KEY.get(event_key)
    if not event:
        # Never silently drop an unfamiliar management event.
        return True, True
    selected = settings.get(event_key, {}) if isinstance(settings, dict) else {}
    if not isinstance(selected, dict):
        selected = {}
    in_app = bool(selected.get("in_app", True))
    push = bool(selected.get("push", event["push_default"]))
    return in_app or event["critical"], push


def settings_for_user(user):
    """Read one user's saved preferences; do not create a row for defaults."""
    try:
        return user.notification_preferences.choices
    except NotificationPreference.DoesNotExist:
        return {}


def settings_for_recipients(user_ids):
    """Batch load settings to avoid one query per recipient."""
    return dict(NotificationPreference.objects.filter(user_id__in=user_ids)
                .values_list("user_id", "choices"))


def validated_choices(post):
    """Only allow predefined events and fields, never arbitrary preference keys."""
    choices = {}
    for key, _, critical, _ in EVENTS:
        choices[key] = {
            "in_app": True if critical else post.get(f"{key}_in_app") == "on",
            "push": post.get(f"{key}_push") == "on",
        }
    return choices
