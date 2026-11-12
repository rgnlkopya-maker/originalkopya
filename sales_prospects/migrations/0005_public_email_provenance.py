from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales_prospects", "0004_guided_search_history")]

    operations = [
        migrations.AddField(
            model_name="prospect", name="email_source_url",
            field=models.URLField(max_length=500, blank=True, default=""),
        ),
    ]
