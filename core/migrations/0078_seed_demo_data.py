import os

from django.core.management import call_command
from django.db import migrations


def seed_demo_data(apps, schema_editor):
    if os.getenv("DEMO_MODE") == "1" and os.getenv("DEMO_SEED_CONFIRM") == "YES":
        call_command("seed_demo")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0077_alter_productionstagecontrolexclusion_control_type"),
    ]

    operations = [
        migrations.RunPython(seed_demo_data, migrations.RunPython.noop),
    ]
