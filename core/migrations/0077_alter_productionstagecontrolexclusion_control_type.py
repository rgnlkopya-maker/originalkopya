from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0076_orderflag_stage_detail"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productionstagecontrolexclusion",
            name="control_type",
            field=models.CharField(
                choices=[
                    ("stage_problem", "Üretim aşama problemi"),
                    ("unshipped_7d", "3 gündür hareket görülmeyen"),
                    ("unshipped_3d_temp", "3 gün geçici gizlenen"),
                ],
                max_length=30,
            ),
        ),
    ]
