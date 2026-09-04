from django.core.management.base import BaseCommand

from product_cards.views import fetch_tcmb_usd_rate


class Command(BaseCommand):
    help = "TCMB'den guncel USD/TRY satis kurunu cekip kaydeder."

    def handle(self, *args, **options):
        rate = fetch_tcmb_usd_rate()
        self.stdout.write(self.style.SUCCESS(f"USD/TRY guncellendi: {rate.usd_try} (TCMB {rate.source_date})"))
