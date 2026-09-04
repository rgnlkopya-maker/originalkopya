from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("product_cards", "0005_exchange_rate_and_usd_costs"),
    ]

    operations = [
        migrations.AddField(
            model_name="productcard",
            name="finansman_maliyeti",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="productcard",
            name="finansman_para_birimi",
            field=models.CharField(choices=[("TRY", "TL"), ("USD", "USD")], default="TRY", max_length=3),
        ),
        migrations.AddField(
            model_name="productcard",
            name="nakis_maliyeti",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="productcard",
            name="nakis_para_birimi",
            field=models.CharField(choices=[("TRY", "TL"), ("USD", "USD")], default="TRY", max_length=3),
        ),
        migrations.AddField(
            model_name="productcard",
            name="paketleme_maliyeti",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="productcard",
            name="paketleme_para_birimi",
            field=models.CharField(choices=[("TRY", "TL"), ("USD", "USD")], default="TRY", max_length=3),
        ),
    ]
