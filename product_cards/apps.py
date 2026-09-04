from django.apps import AppConfig


class ProductCardsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "product_cards"

    def ready(self):
        from . import signals  # noqa: F401
