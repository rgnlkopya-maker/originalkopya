from django.db import migrations, models
import django.db.models.deletion

SNAPSHOT_ORDER_IDS = [44,47,48,49,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,86,87,88,89,90,91,92,96,118,119,120,121,122,132,133,134,137,138,139,140,141,142,143,144,147,148,150,153,154,155,160,161,163,164,165,166,167,168,169,170,171,172,173,174,175,176,177,178,179,180,181,182,186,187,188,189,190,192,195,196,197,198,199,200,202,203,207,208,211,213,214,215,218,236,237,240,241,242,243,244,245,246,247,248,249,250,251,253,255,256,257,258,259,260,262,267,268,269,270,271,272,273,274,275,276,277,279,280,281,282,283,284,287,288,289,290,291,292,293,325,326,328,329,330,331,332,333,336,338,339,340,341,342,343,344,345,347,353,354,355,356,357,363,364,365,366,369,370,371,372,378,379,381,382,383,384,385,386,387,388,389,390,391,392,393,395,396,397,398,399,400,401,402,403,407,409,413,415,416,424,425,482,483,485]
NOTE = "Geçmiş dönemde faturaya bağlandığı bildirildi; MoliApp içinde FT bağlantısı bulunmuyor."

def register_legacy(apps, schema_editor):
    Order = apps.get_model("core", "Order")
    InvoiceLine = apps.get_model("product_cards", "InvoiceLine")
    StandaloneInvoiceLine = apps.get_model("product_cards", "StandaloneInvoiceLine")
    InvoiceFreeDelivery = apps.get_model("product_cards", "InvoiceFreeDelivery")
    Legacy = apps.get_model("product_cards", "LegacyInvoiceAcknowledgement")
    for order_id in SNAPSHOT_ORDER_IDS:
        if not Order.objects.filter(pk=order_id).exists():
            continue
        if InvoiceLine.objects.filter(order_id=order_id).exists():
            continue
        if StandaloneInvoiceLine.objects.filter(order_id=order_id, invoice__is_proforma=False).exists():
            continue
        if InvoiceFreeDelivery.objects.filter(order_id=order_id).exists():
            continue
        Legacy.objects.get_or_create(order_id=order_id, defaults={"note": NOTE})

class Migration(migrations.Migration):
    dependencies = [("product_cards", "0060_invoice_free_delivery")]
    operations = [
        migrations.CreateModel(name="LegacyInvoiceAcknowledgement", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("note", models.TextField(default=NOTE)),
            ("recorded_at", models.DateTimeField(auto_now_add=True)),
            ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="legacy_invoice_acknowledgement", to="core.order")),
        ]),
        migrations.RunPython(register_legacy, migrations.RunPython.noop),
    ]
