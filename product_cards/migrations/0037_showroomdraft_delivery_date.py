from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0036_configure_eylus_demo_product_recipes")]

    operations = [
        migrations.AddField(
            model_name="showroomdraft",
            name="delivery_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
