from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0019_showroom_item_description"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShowroomPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entry_type", models.CharField(choices=[("COLLECTION", "Tahsilat"), ("PROMISE", "Ödeme Sözü")], max_length=12)),
                ("method", models.CharField(blank=True, choices=[("", "Belirtilmedi"), ("CASH", "Nakit"), ("CARD", "Kredi Kartı"), ("CHECK", "Çek"), ("NOTE", "Senet")], default="", max_length=12)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=16)),
                ("payment_date", models.DateField(blank=True, null=True)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("note", models.CharField(blank=True, default="", max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("draft", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payments", to="product_cards.showroomdraft")),
            ],
            options={"ordering": ["due_date", "payment_date", "id"]},
        ),
    ]
