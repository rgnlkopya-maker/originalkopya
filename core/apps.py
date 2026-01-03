from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        import core.signals       # admin ensure (post_migrate)
        import core.signals_qr    # ✅ QR üretimi (post_save)
