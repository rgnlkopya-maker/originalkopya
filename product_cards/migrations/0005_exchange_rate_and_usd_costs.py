from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("product_cards", "0004_cost_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExchangeRate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rate_date", models.DateField(unique=True)),
                ("usd_try", models.DecimalField(decimal_places=6, max_digits=12)),
                ("source_date", models.CharField(blank=True, default="", max_length=20)),
                ("fetched_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-rate_date"]},
        ),
        migrations.AddField(
            model_name="material",
            name="birim_maliyet_para_birimi",
            field=models.CharField(choices=[("TRY", "TL"), ("USD", "USD")], default="TRY", max_length=3),
        ),
        migrations.AlterField(
            model_name="material",
            name="birim_maliyet",
            field=models.DecimalField(decimal_places=4, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="productcard",
            name="iscilik_para_birimi",
            field=models.CharField(choices=[("TRY", "TL"), ("USD", "USD")], default="TRY", max_length=3),
        ),
        migrations.AddField(
            model_name="productcard",
            name="genel_gider_para_birimi",
            field=models.CharField(choices=[("TRY", "TL"), ("USD", "USD")], default="TRY", max_length=3),
        ),
        migrations.AddField(
            model_name="productcard",
            name="diger_maliyet_para_birimi",
            field=models.CharField(choices=[("TRY", "TL"), ("USD", "USD")], default="TRY", max_length=3),
        ),
    ]
