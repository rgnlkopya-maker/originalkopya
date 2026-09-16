from django.db import migrations


def normalize(value):
    return "".join(character for character in (value or "").upper() if character.isalnum())


def match_modazehra_customer(apps, schema_editor):
    Musteri = apps.get_model("core", "Musteri")
    CustomerPricingRule = apps.get_model("core", "CustomerPricingRule")
    for customer in Musteri.objects.all().iterator():
        if normalize(customer.ad) in {"MODAZEHRA", "MODAZEHRADA"}:
            CustomerPricingRule.objects.get_or_create(customer=customer)


class Migration(migrations.Migration):
    dependencies = [("core", "0058_customer_pricing_rule")]
    operations = [
        migrations.RunPython(match_modazehra_customer, migrations.RunPython.noop),
    ]
