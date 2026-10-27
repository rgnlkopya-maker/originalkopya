from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0086_instrument_attachments")]
    operations = [
        migrations.CreateModel(
            name="InstrumentDriveAuthorization",
            fields=[
                ("key", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("encrypted_refresh_token", models.TextField()),
                ("connected_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
