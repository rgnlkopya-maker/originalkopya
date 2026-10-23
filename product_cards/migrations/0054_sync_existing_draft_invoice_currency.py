from django.db import migrations


def sync_existing_unexported_invoice_currencies(apps, schema_editor):
    Invoice = apps.get_model("product_cards", "InvoiceDraft")
    Line = apps.get_model("product_cards", "InvoiceLine")
    Bh = apps.get_model("product_cards", "BizimHesapInvoiceTransfer")
    Ps = apps.get_model("product_cards", "ParasutInvoiceTransfer")
    for invoice in Invoice.objects.filter(status="DRAFT").iterator():
        if Bh.objects.filter(invoice_id=invoice.pk, status__in=("SENT", "SENDING", "UNKNOWN")).exists():
            continue
        if Ps.objects.filter(invoice_id=invoice.pk, status__in=("SENT", "SENDING", "UNKNOWN")).exists():
            continue
        lines = list(Line.objects.filter(invoice_id=invoice.pk).select_related("order"))
        currencies = {(line.order.para_birimi or "TRY") for line in lines}
        if len(currencies) != 1:
            continue
        currency = next(iter(currencies))
        if currency == invoice.currency:
            continue
        if Invoice.objects.filter(customer_id=invoice.customer_id, invoice_date=invoice.invoice_date, currency=currency, status="DRAFT").exclude(pk=invoice.pk).exists():
            continue
        Invoice.objects.filter(pk=invoice.pk).update(currency=currency)


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0053_parasut_deleted_remote_archive")]
    operations = [migrations.RunPython(sync_existing_unexported_invoice_currencies, migrations.RunPython.noop)]
