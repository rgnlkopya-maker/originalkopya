"""Restore White Wedding Afyon folio #124 to draft after verified user request.

Conditionally touches only the identified folio and refuses to change it
if a transfer has occurred or status/customer has changed.
"""
from django.db import migrations


def restore_white_wedding_124(apps, schema_editor):
    Draft = apps.get_model("product_cards", "ShowroomDraft")
    Link = apps.get_model("product_cards", "ShowroomOrderLink")
    row = Draft.objects.filter(
        id=124,
        customer_id=61,
        created_by_id=19,
        status="APPROVED",
        orders_created=False,
    ).first()
    if row is None or Link.objects.filter(draft_id=124).exists():
        return
    row.status = "PENDING"
    row.save(update_fields=["status"])


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0069_showroom_draft_delivery_date")]

    operations = [
        migrations.RunPython(restore_white_wedding_124, migrations.RunPython.noop),
    ]
