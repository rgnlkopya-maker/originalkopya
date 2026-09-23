from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_settings", "0009_systemsettings_staff_access_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccess",
            name="can_view_folio_link",
            field=models.BooleanField(default=False),
        ),
    ]
