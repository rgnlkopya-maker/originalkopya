from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_settings", "0002_personnel_access_defaults"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemsettings",
            name="active_depots",
            field=models.TextField(blank=True, default=""),
        ),
    ]
