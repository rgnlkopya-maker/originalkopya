from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("product_cards", "0059_standalone_order_line"), migrations.swappable_dependency("auth.User")]
    operations = [migrations.CreateModel(name="InvoiceFreeDelivery", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("explanation", models.TextField()),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="auth.user")),
        ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="invoice_free_delivery", to="core.order")),
    ])]
