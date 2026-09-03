from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .admin_init import ensure_admin

@receiver(post_migrate)
def run_ensure_admin(sender, **kwargs):
    # post_migrate her kurulu uygulama için tetiklenir. Yöneticiyi yalnızca
    # core migration'ları tamamlandığında kontrol et.
    if sender.name == "core":
        ensure_admin()
