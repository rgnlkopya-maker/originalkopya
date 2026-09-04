from django.core.exceptions import FieldDoesNotExist
from django.db import models

from core.models import OrderEvent


def sync_order_stage_from_events(order, stage):
    """Silinen bir hareketten sonra yalnızca ilgili aşamanın güncel değerini kurar."""
    try:
        field = order._meta.get_field(stage)
    except FieldDoesNotExist:
        return None

    if not isinstance(field, models.CharField):
        return None

    latest_value = (
        OrderEvent.objects.filter(
            order=order,
            event_type="stage",
            stage=stage,
        )
        .order_by("-timestamp", "-id")
        .values_list("value", flat=True)
        .first()
    )
    value = latest_value if latest_value is not None else field.get_default()
    setattr(order, stage, value)
    order.save(update_fields=[stage])
    return value
