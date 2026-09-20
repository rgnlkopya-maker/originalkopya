from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies = [("core", "0060_order_vat_rate")]
    operations = [
        migrations.CreateModel(
            name="ConsignmentStock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("urun_kodu", models.CharField(db_index=True, max_length=100)),
                ("renk", models.CharField(blank=True, db_index=True, max_length=50, null=True)),
                ("beden", models.CharField(blank=True, db_index=True, max_length=50, null=True)),
                ("quantity_sent", models.PositiveIntegerField(default=1)),
                ("quantity_remaining", models.PositiveIntegerField(default=1)),
                ("cost_snapshot", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("cost_currency", models.CharField(choices=[("TRY","TRY"),("USD","USD"),("EUR","EUR")], default="TRY", max_length=3)),
                ("sent_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("note", models.TextField(blank=True, default="")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="consignment_stocks_created", to=settings.AUTH_USER_MODEL)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="consignment_stocks", to="core.musteri")),
                ("source_order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="consignment_source_stocks", to="core.order")),
            ],
            options={"ordering":["sent_at","id"]},
        ),
        migrations.CreateModel(
            name="ConsignmentMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("movement_type", models.CharField(choices=[("IN","Konsinye Giriş"),("USE","Siparişte Kullanıldı"),("RETURN","İade")], max_length=10)),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("note", models.TextField(blank=True, default="")),
                ("stock", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="core.consignmentstock")),
                ("target_order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="consignment_movements", to="core.order")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["-created_at","-id"]},
        ),
        migrations.AddIndex(model_name="consignmentstock", index=models.Index(fields=["customer","urun_kodu","renk","beden"], name="core_consig_cust_prod_idx")),
    ]
