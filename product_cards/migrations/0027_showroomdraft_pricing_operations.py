from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("product_cards","0026_showroomdraft_order_type")]
    operations=[
        migrations.AddField(
            model_name="showroomdraft",
            name="pricing_operations",
            field=models.JSONField(blank=True,default=list),
        ),
        migrations.AddField(
            model_name="showroomdraft",
            name="folio_adjustment_target",
            field=models.DecimalField(blank=True,decimal_places=2,max_digits=16,null=True),
        ),
    ]
