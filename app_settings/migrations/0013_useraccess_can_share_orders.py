from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app_settings", "0012_fix_sevkiyat_finans_favorite_title"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccess",
            name="can_share_orders",
            field=models.BooleanField(default=False),
        ),
    ]
