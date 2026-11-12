from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales_prospects", "0002_outreach_email")]
    operations = [
        migrations.AddField(model_name="prospect", name="phone_number", field=models.CharField(blank=True, default="", max_length=30)),
        migrations.AddField(model_name="prospect", name="whatsapp_number", field=models.CharField(blank=True, default="", max_length=30)),
        migrations.AddField(model_name="prospect", name="phone_source_url", field=models.URLField(blank=True, default="", max_length=500)),
        migrations.AddField(model_name="prospect", name="whatsapp_source_url", field=models.URLField(blank=True, default="", max_length=500)),
        migrations.AddField(model_name="prospect", name="instagram_source_url", field=models.URLField(blank=True, default="", max_length=500)),
        migrations.AddField(model_name="prospect", name="contact_scan_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="prospect", name="contact_scan_note", field=models.CharField(blank=True, default="", max_length=250)),
    ]
