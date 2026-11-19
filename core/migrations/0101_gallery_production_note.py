from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def preserve_existing_production_notes(apps, schema_editor):
    """Copy previously saved text into individual note entries without changing source data."""
    Group = apps.get_model("core", "GalleryGroup")
    Note = apps.get_model("core", "GalleryProductionNote")
    database = schema_editor.connection.alias
    for group in Group.objects.using(database).exclude(production_notes="").iterator(chunk_size=100):
        if group.production_notes.strip():
            Note.objects.using(database).create(
                group_id=group.pk, body=group.production_notes,
                created_at=django.utils.timezone.now()
            )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0100_gallery_group_photos_notes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="GalleryProductionNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField(max_length=5000)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="gallery_notes", to=settings.AUTH_USER_MODEL)),
                ("deleted_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="gallery_notes_deleted", to=settings.AUTH_USER_MODEL)),
                ("group", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="note_entries", to="core.gallerygroup")),
            ],
            options={"ordering": ["created_at", "pk"]},
        ),
        migrations.RunPython(preserve_existing_production_notes, migrations.RunPython.noop),
    ]
