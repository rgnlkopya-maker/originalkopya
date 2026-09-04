from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("product_cards", "0002_productcard_image_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="material",
            name="image_url",
            field=models.URLField(blank=True, default=""),
        ),
    ]
