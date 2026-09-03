from django.db import migrations, models


URUN_TIPI_CHOICES = [
    ("BALIK", "Balık"),
    ("HELEN", "Helen"),
    ("ETEKLI_BALIK", "Etekli Balık"),
    ("TESETTUR_BALIK", "Tesettür Balık"),
    ("TESETTUR_ETEKLI_BALIK", "Tesettür Etekli Balık"),
    ("TESETTUR_HELEN", "Tesettür Helen"),
    ("DIGER", "Diğer"),
]


class Migration(migrations.Migration):
    dependencies = [("core", "0049_order_is_active")]

    operations = [
        migrations.AddField(
            model_name="urunkod",
            name="urun_tipi",
            field=models.CharField(
                blank=True, choices=URUN_TIPI_CHOICES, default="", max_length=30
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="urun_tipi",
            field=models.CharField(
                blank=True,
                choices=URUN_TIPI_CHOICES,
                db_index=True,
                default="",
                max_length=30,
            ),
        ),
    ]
