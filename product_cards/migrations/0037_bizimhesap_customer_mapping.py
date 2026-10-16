from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0036_approved_unshipped_vat_10"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="BizimHesapCustomerMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_customer_id", models.CharField(max_length=100)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("confirmed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("customer", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="bizimhesap_mapping", to="core.musteri")),
            ],
        ),
        migrations.AddConstraint(
            model_name="bizimhesapcustomermapping",
            constraint=models.UniqueConstraint(fields=("external_customer_id",), name="unique_bizimhesap_customer_id"),
        ),
    ]
