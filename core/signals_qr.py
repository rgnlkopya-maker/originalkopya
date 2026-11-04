from contextlib import contextmanager
from contextvars import ContextVar
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
from .qr import ensure_order_qr


_suspend_qr = ContextVar("suspend_order_qr", default=False)


@contextmanager
def suspend_order_qr():
    token = _suspend_qr.set(True)
    try:
        yield
    finally:
        _suspend_qr.reset(token)


@receiver(post_save, sender=Order)
def create_qr(sender, instance, created, **kwargs):
    if created and not instance.qr_code_url and not _suspend_qr.get():
        ensure_order_qr(instance)
