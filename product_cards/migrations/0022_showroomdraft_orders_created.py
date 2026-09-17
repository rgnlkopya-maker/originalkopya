from django.db import migrations, models


def mark_transferred_folios(apps, schema_editor):
    ShowroomDraft = apps.get_model("product_cards", "ShowroomDraft")
    ShowroomDraft.objects.filter(status="TRANSFERRED").update(orders_created=True)


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0021_fix_legacy_showroomfolio_fk")]

    operations = [
        migrations.AddField(
            model_name="showroomdraft",
            name="orders_created",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_transferred_folios, migrations.RunPython.noop),
    ]
