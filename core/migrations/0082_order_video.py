from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("core", "0081_order_print_tracking")]
    operations = [
        migrations.CreateModel(
            name="OrderVideo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("video_url", models.URLField(max_length=1200)),
                ("original_name", models.CharField(max_length=255, blank=True, default="")),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="videos", to="core.order")),
            ],
        ),
    ]
