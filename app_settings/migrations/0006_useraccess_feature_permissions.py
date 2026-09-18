from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app_settings", "0005_grant_tahir_create_orders"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccess",
            name="feature_permissions",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
