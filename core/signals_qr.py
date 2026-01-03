from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
from .qr import ensure_order_qr


@receiver(post_save, sender=Order)
def create_qr(sender, instance, created, **kwargs):
    if created and not instance.qr_code_url:
        ensure_order_qr(instance)
