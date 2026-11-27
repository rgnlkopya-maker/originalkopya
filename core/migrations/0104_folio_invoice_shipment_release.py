from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0103_document_archive")]

    operations = [
        migrations.AddField(
            model_name="order",
            name="invoice_shipment_release_on",
            field=models.DateField(blank=True, editable=False, null=True),
        ),
    ]
