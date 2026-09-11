from django.conf import settings
from django.db import migrations
from django.utils import timezone


def mark_existing_orders_seen(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Order = apps.get_model("core", "Order")
    OrderSeen = apps.get_model("core", "OrderSeen")

    user_ids = list(User.objects.filter(is_active=True).values_list("id", flat=True))
    order_ids = list(Order.objects.values_list("id", flat=True))
    seen_time = timezone.now()
    OrderSeen.objects.bulk_create(
        [
            OrderSeen(user_id=user_id, order_id=order_id, seen_time=seen_time)
            for user_id in user_ids
            for order_id in order_ids
        ],
        ignore_conflicts=True,
        batch_size=1000,
    )


class Migration(migrations.Migration):
    dependencies = [("core", "0054_reminder_reminderstate")]

    operations = [migrations.RunPython(mark_existing_orders_seen, migrations.RunPython.noop)]
