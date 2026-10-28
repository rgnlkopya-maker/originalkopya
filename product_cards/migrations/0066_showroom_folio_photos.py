from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0065_reset_verified_ft66_ft67_bizimhesap")]
    operations = [
        migrations.CreateModel(
            name="ShowroomFolioPhoto",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("storage_path", models.CharField(max_length=500, unique=True)),
                ("original_name", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("draft", models.ForeignKey(to="product_cards.showroomdraft", on_delete=django.db.models.deletion.CASCADE, related_name="source_photos")),
            ],
        ),
    ]
