from django.db import migrations, models
import django.db.models.deletion

def initialize_numbers(apps,schema_editor):
    Draft=apps.get_model("product_cards","InvoiceDraft")
    Manual=apps.get_model("product_cards","StandaloneInvoice")
    Number=apps.get_model("product_cards","SharedInvoiceNumber")
    Sequence=apps.get_model("product_cards","InvoiceNumberSequence")
    from django.db.models import Max
    maximum=Draft.objects.aggregate(n=Max("id"))["n"] or 0
    Number.objects.bulk_create([Number(number=d.id,draft_id=d.id) for d in Draft.objects.all()])
    for inv in Manual.objects.filter(is_proforma=False).order_by("created_at","id"):
        maximum+=1
        Number.objects.create(number=maximum,manual_id=inv.id)
    Sequence.objects.create(pk=1,last_number=maximum)

class Migration(migrations.Migration):
    dependencies=[("product_cards","0061_legacy_invoice_acknowledgement")]
    operations=[
      migrations.CreateModel(name="InvoiceNumberSequence",fields=[("id",models.BigAutoField(primary_key=True,serialize=False)),("last_number",models.PositiveIntegerField(default=0))]),
      migrations.CreateModel(name="SharedInvoiceNumber",fields=[
         ("id",models.BigAutoField(primary_key=True,serialize=False)),
         ("number",models.PositiveIntegerField(unique=True)),
         ("draft",models.OneToOneField(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name="shared_number",to="product_cards.invoicedraft")),
         ("manual",models.OneToOneField(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name="shared_number",to="product_cards.standaloneinvoice"))
      ]),
      migrations.RunPython(initialize_numbers,migrations.RunPython.noop)
    ]
