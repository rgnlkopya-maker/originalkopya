from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0050_urunkod_urun_tipi_order_urun_tipi")]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="siparis_tipi",
            field=models.CharField(
                blank=True,
                choices=[
                    ("OZEL", "Özel"),
                    ("SERI", "Seri"),
                    ("TEKLI", "Tekli Sipariş"),
                    ("STOK", "Stoğa Üretim"),
                ],
                db_index=True,
                max_length=20,
                null=True,
            ),
        ),
    ]
