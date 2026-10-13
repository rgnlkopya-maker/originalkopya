from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0077_alter_productionstagecontrolexclusion_control_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="satis_kuru",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                help_text="Siparis olusturulurken sabitlenen satis doviz kuru",
                max_digits=12,
                null=True,
            ),
        ),
    ]
