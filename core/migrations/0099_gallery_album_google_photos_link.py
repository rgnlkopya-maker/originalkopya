from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0098_gallery_thumbnail")]

    operations = [
        migrations.AddField(
            model_name="galleryalbum",
            name="google_photos_url",
            field=models.URLField(max_length=1000, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="galleryalbum",
            name="cover_data_url",
            field=models.TextField(blank=True, default=""),
        ),
    ]
