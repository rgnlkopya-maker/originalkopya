from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("product_cards", "0052_parasut_pending_sync")]
    operations = [
        migrations.AddField(model_name="parasutinvoicetransfer", name="deleted_external_invoice_id", field=models.CharField(max_length=100, blank=True, default="")),
        migrations.AddField(model_name="parasutinvoicetransfer", name="deleted_verified_at", field=models.DateTimeField(null=True, blank=True)),
    ]
