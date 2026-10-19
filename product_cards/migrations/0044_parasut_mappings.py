from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('product_cards', '0043_parasut_invoice_transfer')]

    operations = [
        migrations.CreateModel(
            name='ParasutCustomerMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_contact_id', models.CharField(max_length=100, unique=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='parasut_mapping', to='core.musteri')),
            ],
        ),
        migrations.CreateModel(
            name='ParasutProductMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('product_code', models.CharField(max_length=150, unique=True)),
                ('external_product_id', models.CharField(max_length=100, unique=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
