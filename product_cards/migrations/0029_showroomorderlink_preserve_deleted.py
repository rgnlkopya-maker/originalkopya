from django.db import migrations, models
import django.db.models.deletion


def fill_order_numbers(apps, schema_editor):
    Link = apps.get_model("product_cards", "ShowroomOrderLink")
    for link in Link.objects.select_related("order").all():
        if link.order_id and not link.order_number:
            link.order_number = link.order.siparis_numarasi or ""
            link.save(update_fields=["order_number"])


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0028_showroomorderlink"),
    ]

    operations = [
        migrations.AddField(
            model_name="showroomorderlink",
            name="order_number",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AlterField(
            model_name="showroomorderlink",
            name="order",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="showroom_link", to="core.order"),
        ),
        migrations.RunPython(fill_order_numbers, migrations.RunPython.noop),
    ]
