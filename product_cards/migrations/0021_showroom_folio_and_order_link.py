from django.db import migrations, models
import django.db.models.deletion


def backfill_folios(apps, schema_editor):
    ShowroomDraft = apps.get_model("product_cards", "ShowroomDraft")
    ShowroomFolio = apps.get_model("product_cards", "ShowroomFolio")
    number = 1
    for draft in ShowroomDraft.objects.order_by("created_at", "id").iterator():
        ShowroomFolio.objects.get_or_create(draft_id=draft.id, defaults={"number": number})
        number += 1


def reverse_backfill(apps, schema_editor):
    ShowroomFolio = apps.get_model("product_cards", "ShowroomFolio")
    ShowroomFolio.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0020_showroompayment"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShowroomFolio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.PositiveIntegerField(db_index=True, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("draft", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="folio", to="product_cards.showroomdraft")),
            ],
            options={"ordering": ["number"]},
        ),
        migrations.CreateModel(
            name="ShowroomOrderLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("draft", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="order_links", to="product_cards.showroomdraft")),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="showroom_source", to="core.order")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.RunPython(backfill_folios, reverse_backfill),
    ]
