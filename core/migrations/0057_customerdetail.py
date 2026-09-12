from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0056_auditlog"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerDetail",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("yetkili_kisi", models.CharField(blank=True, default="", max_length=150)),
                ("telefon", models.CharField(blank=True, default="", max_length=40)),
                ("telefon_2", models.CharField(blank=True, default="", max_length=40)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("ulke", models.CharField(blank=True, default="", max_length=100)),
                ("adres", models.TextField(blank=True, default="")),
                ("teslimat_adresi", models.TextField(blank=True, default="")),
                ("fatura_adresi", models.TextField(blank=True, default="")),
                ("dis_ticaret_firmasi", models.CharField(blank=True, default="", max_length=200)),
                ("notlar", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="customer_detail", to="core.musteri")),
            ],
            options={
                "verbose_name": "Müşteri Detayı",
                "verbose_name_plural": "Müşteri Detayları",
            },
        ),
    ]
