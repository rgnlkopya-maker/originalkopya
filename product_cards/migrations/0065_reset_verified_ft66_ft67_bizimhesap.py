from django.db import migrations


def reset_verified_rejected_bizimhesap_transfers(apps, schema_editor):
    """The operator confirmed FT-66 and FT-67 are absent in BizimHesap.

    Only unlock these two specific address-rejected attempts; never resend automatically.
    """
    Transfer = apps.get_model("product_cards", "BizimHesapInvoiceTransfer")
    Transfer.objects.filter(
        invoice_id__in=[66, 67],
        status="UNKNOWN",
        external_invoice_id="",
        external_invoice_no="",
        last_error="BizimHesap reddetti: Adres bilgisi gönderilmemiş",
    ).update(
        status="NOT_SENT",
        last_error="",
        payload_fingerprint="",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0064_invoice_manual_lines"),
    ]

    operations = [
        migrations.RunPython(
            reset_verified_rejected_bizimhesap_transfers,
            migrations.RunPython.noop,
        ),
    ]
