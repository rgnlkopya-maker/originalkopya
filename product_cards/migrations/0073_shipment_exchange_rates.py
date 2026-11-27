from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0072_lace_movement_choices")]

    operations = [
        migrations.AddField(
            model_name="shipmentfinancialsnapshot",
            name="eur_try",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="shipmentfinancialsnapshot",
            name="gbp_try",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="shipmentfinancialsnapshot",
            name="fx_reference_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
