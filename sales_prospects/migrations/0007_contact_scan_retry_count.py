from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales_prospects", "0006_sequential_results_and_instagram_followers")]
    operations = [
        migrations.AddField(
            model_name="prospect", name="contact_scan_attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
