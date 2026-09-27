from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0071_todoitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="maliyet_indirimi",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
    ]
