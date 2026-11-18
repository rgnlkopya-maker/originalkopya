from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import UrunKod, GalleryAlbum

@receiver(post_save, sender=UrunKod)
def ensure_product_gallery(sender, instance, **kwargs):
    GalleryAlbum.objects.get_or_create(code=instance.kod)
