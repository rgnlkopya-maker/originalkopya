from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0002_attendancerecord_status_note_report_image_url"),
    ]

    operations = [
        migrations.AlterField(
            model_name="attendancerecord",
            name="status",
            field=models.CharField(
                choices=[
                    ("worked", "Çalıştı"),
                    ("leave", "İzinli"),
                    ("annual_leave", "Yıllık İzin"),
                    ("sick", "Raporlu"),
                    ("other", "Diğer"),
                ],
                default="worked",
                max_length=20,
            ),
        ),
    ]
