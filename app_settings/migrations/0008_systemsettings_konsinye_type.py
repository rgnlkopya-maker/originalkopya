from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("app_settings","0007_useraccess_data_scope")]
    operations=[
        migrations.AlterField(
            model_name="systemsettings",
            name="default_order_type",
            field=models.CharField(
                choices=[("SERI","Seri"),("TEKLI","Tekli Sipariş"),("STOK","Stoğa Üretim"),("KONSINYE","Konsinye"),("OZEL","Özel Sipariş")],
                default="SERI",
                max_length=20,
            ),
        ),
    ]
