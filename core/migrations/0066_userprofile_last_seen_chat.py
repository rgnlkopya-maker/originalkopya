from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0065_chat_whatsapp_features"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="last_seen_chat",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
