from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0068_showroom_pending_ocr_items")]

    operations = [
        migrations.AddField(
            model_name="showroomdraft",
            name="delivery_date",
            field=models.DateField(null=True, blank=True),
        ),
    ]
