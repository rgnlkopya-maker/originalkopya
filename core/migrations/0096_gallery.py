from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("core", "0095_customer_monitor_state")]
    operations = [
        migrations.CreateModel(name="GalleryAlbum", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("code", models.CharField(max_length=80, unique=True)), ("created_at", models.DateTimeField(auto_now_add=True))]),
        migrations.CreateModel(name="GalleryGroup", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("name", models.CharField(max_length=160)), ("created_at", models.DateTimeField(auto_now_add=True)), ("album", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="groups", to="core.galleryalbum"))]),
        migrations.CreateModel(name="GalleryMedia", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("storage_path", models.CharField(max_length=500, unique=True)), ("original_name", models.CharField(max_length=255)), ("content_type", models.CharField(max_length=100)), ("is_cover", models.BooleanField(default=False)), ("created_at", models.DateTimeField(auto_now_add=True)), ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="media", to="core.gallerygroup"))]),
        migrations.AddConstraint(model_name="gallerygroup", constraint=models.UniqueConstraint(fields=("album", "name"), name="gallery_unique_album_group")),
    ]
