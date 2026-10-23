from django.db import migrations


VERIFIED_NUMBERS = {
    23: "ML02026000001823",
    28: "ML02026000001822",
    30: "ML02026000001824",
}


def restore_verified_numbers(apps, schema_editor):
    InvoiceDraft = apps.get_model("product_cards", "InvoiceDraft")
    db = schema_editor.connection.alias
    for invoice_id, number in VERIFIED_NUMBERS.items():
        # Do not overwrite any number a user may have entered since verification.
        invoice = InvoiceDraft.objects.using(db).get(pk=invoice_id)
        if invoice.official_number == number:
            continue
        if invoice.status != "FINAL" or invoice.official_number:
            raise RuntimeError(
                "Official number recovery aborted: invoice %s changed; no unverified overwrite." % invoice_id
            )
        invoice.official_number = number
        invoice.save(update_fields=["official_number"])


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0049_invoice_aktarilmayacak_status")]
    operations = [migrations.RunPython(restore_verified_numbers, migrations.RunPython.noop)]
