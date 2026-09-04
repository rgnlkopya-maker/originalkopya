from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendancerecord",
            name="status",
            field=models.CharField(
                choices=[
                    ("worked", "Çalıştı"),
                    ("leave", "İzinli"),
                    ("sick", "Raporlu"),
                    ("other", "Diğer"),
                ],
                default="worked",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="note",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="report_image_url",
            field=models.URLField(blank=True, default=""),
        ),
    ]
