from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import UrunKod
from .models import ProductCard


@receiver(post_save, sender=UrunKod)
def ensure_product_card(sender, instance, **kwargs):
    ProductCard.objects.get_or_create(urun=instance)
