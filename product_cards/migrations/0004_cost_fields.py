from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("product_cards", "0003_material_image_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="material",
            name="birim_maliyet",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="productcard",
            name="iscilik_maliyeti",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="productcard",
            name="genel_gider",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="productcard",
            name="diger_maliyet",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
    ]
