from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("planning", "0003_multiple_planning_entries_per_day"),
    ]

    operations = [
        migrations.AddField(
            model_name="shipmentplan",
            name="invoiced",
            field=models.BooleanField(default=False),
        ),
    ]
