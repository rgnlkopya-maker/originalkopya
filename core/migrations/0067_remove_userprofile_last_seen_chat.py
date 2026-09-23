from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0066_userprofile_last_seen_chat"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="userprofile",
            name="last_seen_chat",
        ),
    ]
