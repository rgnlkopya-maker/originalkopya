from django.core.management.base import BaseCommand
from product_cards.missing_shipment_costs import fill_missing_shipment_costs


class Command(BaseCommand):
    help = "Preview or fill historical shipments whose original product cost was missing."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist eligible fixes (default: dry-run).")
        parser.add_argument("--product-code", default=None, help="Restrict to one product code.")

    def handle(self, *args, **options):
        count = fill_missing_shipment_costs(options["product_code"], apply=options["apply"])
        mode = "Updated" if options["apply"] else "Eligible (dry run)"
        self.stdout.write(f"{mode}: {count} shipment snapshots")
