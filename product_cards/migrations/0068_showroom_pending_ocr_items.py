from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0067_allow_shared_external_customer_mappings")]

    operations = [
        migrations.AddField(
            model_name="showroomdraft",
            name="import_pending_items",
            field=models.JSONField(default=list, blank=True),
        ),
    ]
