from django.db import migrations, models


def preserve_standard_album(apps, schema_editor):
    Album = apps.get_model("core", "GalleryAlbum")
    Group = apps.get_model("core", "GalleryGroup")
    using = schema_editor.connection.alias
    for album in Album.objects.using(using).all().iterator(chunk_size=100):
        existing = (Group.objects.using(using)
                    .filter(album_id=album.pk, name__in=["Standart Model", "Standart"])
                    .order_by("id").first())
        if existing is None:
            Group.objects.using(using).create(
                album_id=album.pk, name="Standart Model",
                cover_data_url=album.cover_data_url, google_photos_url=album.google_photos_url)
        else:
            changes = {}
            if album.cover_data_url and not existing.cover_data_url:
                changes["cover_data_url"] = album.cover_data_url
            if album.google_photos_url and not existing.google_photos_url:
                changes["google_photos_url"] = album.google_photos_url
            if changes:
                Group.objects.using(using).filter(pk=existing.pk).update(**changes)


class Migration(migrations.Migration):
    dependencies = [("core", "0099_gallery_album_google_photos_link")]
    operations = [
        migrations.AddField(model_name="gallerygroup", name="google_photos_url",
                            field=models.URLField(max_length=1000, blank=True, default="")),
        migrations.AddField(model_name="gallerygroup", name="cover_data_url",
                            field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="gallerygroup", name="production_notes",
                            field=models.TextField(blank=True, default="")),
        migrations.RunPython(preserve_standard_album, migrations.RunPython.noop),
    ]
