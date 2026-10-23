from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0047_invoice_status_history")]
    operations = [
        migrations.AddField(model_name="invoicedraft", name="bizimhesap_display_status", field=models.CharField(max_length=8, blank=True, default="", choices=[("", "Otomatik"), ("no", "İşlenmedi"), ("yes", "Elle İşlendi"), ("api", "API ile Aktarıldı")])),
        migrations.AddField(model_name="invoicedraft", name="parasut_display_status", field=models.CharField(max_length=8, blank=True, default="", choices=[("", "Otomatik"), ("no", "İşlenmedi"), ("yes", "Elle İşlendi"), ("api", "API ile Aktarıldı")])),
    ]
