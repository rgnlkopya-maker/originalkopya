from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales_prospects", "0005_public_email_provenance")]

    operations = [
        migrations.AddField(
            model_name="prospect", name="instagram_followers",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="prospect", name="instagram_followers_source",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="guidedsearch", name="next_page",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="guidedsearch", name="last_page_size",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="guidedsearch", name="exhausted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="guidedsearch", name="last_error",
            field=models.CharField(blank=True, default="", max_length=400),
        ),
        migrations.AddField(
            model_name="guidedsearch", name="search_provider",
            field=models.CharField(default="SERPER", max_length=20),
        ),
    ]
