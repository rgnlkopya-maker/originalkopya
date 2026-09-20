from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("core","0061_consignment_stock")]
    operations=[
        migrations.AlterField(
            model_name="order",
            name="siparis_tipi",
            field=models.CharField(
                blank=True,
                choices=[("OZEL","Özel"),("SERI","Seri"),("TEKLI","Tekli Sipariş"),("STOK","Stoğa Üretim"),("KONSINYE","Konsinye")],
                db_index=True,
                max_length=20,
                null=True,
            ),
        ),
    ]
