"""Management-only operational alerts.

Notifications are stored for authorized managers; browser push is sent only
after the originating database transaction commits.
"""
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver

from .backup_center_models import BackupExecution
from .models import Notification, OrderEvent, OrderFlag

logger = logging.getLogger(__name__)


def management_users():
    return get_user_model().objects.filter(is_active=True).filter(
        Q(is_superuser=True) | Q(groups__name__in=["patron", "mudur"])
    ).distinct()


def notify_management(title, message, url, *, order=None, exclude_user_ids=()):
    excluded = set(exclude_user_ids)
    for recipient in management_users():
        if recipient.pk in excluded:
            continue
        Notification.objects.create(
            user=recipient, order=order, title=title, message=message
        )
        recipient_id = recipient.pk

        def deliver(uid=recipient_id):
            try:
                from .push_views import send_push_to_user
                user = get_user_model().objects.filter(pk=uid, is_active=True).first()
                if user:
                    send_push_to_user(
                        user, title, message, url=url,
                        tag=f"moli-manager-{order.pk if order else 'system'}-{title[:20]}"
                    )
            except Exception:
                logger.exception("Management push failed for user %s", uid)

        transaction.on_commit(deliver)


@receiver(post_save, sender=OrderEvent)
def notify_management_on_order_event(sender, instance, created, **kwargs):
    if not created or instance.event_type != "stage":
        return
    order = instance.order
    customer = order.musteri.ad if order.musteri_id else "Stoğa Üretim"
    summary = f"{order.siparis_numarasi} | {customer} | {order.urun_kodu or '—'} {order.renk or ''} {order.beden or ''}".strip()

    # Only an actual completed shipment can add a new row to the reconciliation page.
    if instance.stage == "sevkiyat_durum" and instance.value == "gonderildi":
        from product_cards.invoice_models import InvoiceLine, StandaloneInvoiceLine, InvoiceFreeDelivery, LegacyInvoiceAcknowledgement
        outstanding = (
            not InvoiceLine.objects.filter(order=order).exists()
            and not StandaloneInvoiceLine.objects.filter(order=order, invoice__is_proforma=False).exists()
            and not InvoiceFreeDelivery.objects.filter(order=order).exists()
            and not LegacyInvoiceAcknowledgement.objects.filter(order=order).exists()
        )
        if outstanding:
            notify_management(
                "Faturaya Aktarılmayan Yeni Sevkiyat",
                summary,
                "/urun-kartlari/faturalar/aktarilmayan-sevkler/",
                order=None,
            )

    flags = list(OrderFlag.objects.filter(order=order, is_active=True).prefetch_related("notify_users"))
    if flags:
        # The existing flag handler already notifies explicitly selected users.
        # Only add managers not already in that recipient set.
        existing = set()
        for flag in flags:
            existing.update(flag.notify_users.values_list("pk", flat=True))
        notify_management(
            "Bayraklı Siparişte Üretim Hareketi",
            f"{summary} | {instance.stage}: {instance.value} | İşlemi yapan: {instance.user}",
            f"/order/{order.pk}/",
            order=order,
            exclude_user_ids=existing,
        )


@receiver(post_save, sender=BackupExecution)
def notify_management_on_backup_failure(sender, instance, created, **kwargs):
    if created or not instance.completed_at or instance.success:
        return
    # Only the transition from unfinished to failed is notified. Later edits
    # to a failed backup must not create new notifications.
    if Notification.objects.filter(
        title="Otomatik Yedekleme Başarısız",
        message__startswith=f"Yedek #{instance.pk} |",
    ).exists():
        return
    label = dict(instance._meta.get_field("module").choices).get(instance.module, instance.module)
    notify_management(
        "Otomatik Yedekleme Başarısız",
        f"Yedek #{instance.pk} | {label} | {instance.message or 'Yedek oluşturulamadı.'}",
        "/yonetim/yedekleme-merkezi/",
    )
