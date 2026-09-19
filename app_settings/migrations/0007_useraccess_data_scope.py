from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app_settings", "0006_useraccess_feature_permissions"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccess",
            name="data_scope",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
