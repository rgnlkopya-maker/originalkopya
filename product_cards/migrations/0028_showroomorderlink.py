from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0027_showroomdraft_pricing_operations"),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShowroomOrderLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("draft", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="order_links", to="product_cards.showroomdraft")),
                ("draft_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_links", to="product_cards.showroomdraftitem")),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="showroom_link", to="core.order")),
            ],
            options={"ordering": ["id"]},
        ),
    ]
