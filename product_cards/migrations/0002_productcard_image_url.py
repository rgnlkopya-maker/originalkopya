from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="productcard",
            name="image_url",
            field=models.URLField(blank=True, default=""),
        ),
    ]
