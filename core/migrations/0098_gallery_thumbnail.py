from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0097_gallery_media_order")]

    operations = [
        migrations.AddField(
            model_name="gallerymedia",
            name="thumbnail_path",
            field=models.CharField(max_length=500, blank=True, default=""),
        ),
    ]
