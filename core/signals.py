from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .admin_init import ensure_admin

@receiver(post_migrate)
def run_ensure_admin(sender, **kwargs):
    ensure_admin()
