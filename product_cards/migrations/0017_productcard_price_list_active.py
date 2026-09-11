from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0016_price_list_settings")]

    operations = [
        migrations.AddField(
            model_name="productcard",
            name="price_list_active",
            field=models.BooleanField(default=True),
        ),
    ]
