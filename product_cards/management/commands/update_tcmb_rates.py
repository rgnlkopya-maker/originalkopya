from django.core.management.base import BaseCommand

from product_cards.views import fetch_tcmb_usd_rate
from product_cards.price_list_views import fetch_price_list_tcmb_rates


class Command(BaseCommand):
    help = "TCMB'den guncel USD/TRY satis kurunu cekip kaydeder."

    def handle(self, *args, **options):
        fetch_tcmb_usd_rate()
        rate = fetch_price_list_tcmb_rates()
        self.stdout.write(self.style.SUCCESS(
            f"USD/TRY {rate.usd_try} ve EUR/TRY {rate.eur_try} guncellendi (TCMB {rate.source_date})"
        ))
