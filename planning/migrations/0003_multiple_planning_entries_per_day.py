from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("planning", "0002_shipmentplan"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="planningentry",
            name="unique_planning_section_date",
        ),
        migrations.AlterModelOptions(
            name="planningentry",
            options={"ordering": ["date", "section", "id"]},
        ),
    ]
