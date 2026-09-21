from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_settings", "0008_systemsettings_konsinye_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemsettings",
            name="staff_access_enabled",
            field=models.BooleanField(default=True),
        ),
    ]
