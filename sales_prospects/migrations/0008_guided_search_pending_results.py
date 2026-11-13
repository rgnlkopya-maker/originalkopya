from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales_prospects", "0007_contact_scan_retry_count")]
    operations = [
        migrations.AddField(
            model_name="guidedsearch", name="pending_results",
            field=models.JSONField(default=list, blank=True),
        ),
    ]
