from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("product_cards","0025_showroomdraft_previous_balance")]
    operations=[
        migrations.AddField(
            model_name="showroomdraft",
            name="order_type",
            field=models.CharField(
                choices=[("OZEL","Özel"),("SERI","Seri"),("TEKLI","Tekli Sipariş"),("STOK","Stoğa Üretim"),("KONSINYE","Konsinye")],
                default="SERI",
                max_length=20,
            ),
        ),
    ]
