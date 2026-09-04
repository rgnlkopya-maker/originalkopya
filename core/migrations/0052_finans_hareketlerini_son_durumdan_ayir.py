from django.db import migrations


def finance_events_are_not_status(apps, schema_editor):
    OrderEvent = apps.get_model("core", "OrderEvent")
    OrderEvent.objects.filter(stage="finans_hareketi").update(event_type="order_update")


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0051_alter_order_siparis_tipi"),
    ]

    operations = [
        migrations.RunPython(finance_events_are_not_status, reverse_noop),
    ]
