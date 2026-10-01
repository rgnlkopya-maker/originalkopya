from django.core.management.base import BaseCommand

from product_cards.views import recalculate_approved_product_costs
from product_cards.price_list_views import fetch_price_list_tcmb_rates


class Command(BaseCommand):
    help = "TCMB'den guncel USD, EUR ve GBP satis kurlarini cekip kaydeder."

    def handle(self, *args, **options):
        # TCMB'ye tek istek: USD, EUR ve GBP birlikte alinir.
        rate = fetch_price_list_tcmb_rates()
        updated = recalculate_approved_product_costs(rate.usd_try)
        self.stdout.write(self.style.SUCCESS(
            f"USD/TRY {rate.usd_try}, EUR/TRY {rate.eur_try} ve GBP/TRY {rate.gbp_try} guncellendi "
            f"(TCMB {rate.source_date}); {updated} onayli urun maliyeti yenilendi."
        ))
