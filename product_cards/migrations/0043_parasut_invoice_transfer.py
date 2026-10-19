from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('product_cards', '0042_invoice_manual_platform_status')]

    operations = [
        migrations.CreateModel(
            name='ParasutInvoiceTransfer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(max_length=16, default='NOT_SENT', choices=[('NOT_SENT', 'Gönderilmedi'), ('SENDING', 'Gönderiliyor'), ('SENT', "Paraşüt'e kaydedildi"), ('UNKNOWN', 'Kontrol gerekli')])),
                ('external_invoice_id', models.CharField(max_length=100, blank=True, default='')),
                ('external_invoice_no', models.CharField(max_length=100, blank=True, default='')),
                ('official_number_synced_at', models.DateTimeField(null=True, blank=True)),
                ('payload_fingerprint', models.CharField(max_length=64, blank=True, default='')),
                ('last_error', models.CharField(max_length=255, blank=True, default='')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('invoice', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='parasut_transfer', to='product_cards.invoicedraft')),
            ],
        ),
    ]
