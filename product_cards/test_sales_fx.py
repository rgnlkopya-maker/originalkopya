from decimal import Decimal
from django.test import SimpleTestCase

from .sales_fx import sale_amount_in_try


class SalesFxConversionTests(SimpleTestCase):
    def test_tl_does_not_need_exchange_rate(self):
        self.assertEqual(sale_amount_in_try("13000", "TRY"), Decimal("13000.00"))

    def test_usd_manual_rate(self):
        self.assertEqual(sale_amount_in_try("300", "USD", "45"), Decimal("13500.00"))

    def test_eur_and_gbp(self):
        self.assertEqual(sale_amount_in_try("100", "EUR", "50"), Decimal("5000.00"))
        self.assertEqual(sale_amount_in_try("100", "GBP", "60"), Decimal("6000.00"))

    def test_missing_foreign_rate_is_rejected(self):
        with self.assertRaises(ValueError):
            sale_amount_in_try("300", "USD")

    def test_zero_rate_is_rejected(self):
        with self.assertRaises(ValueError):
            sale_amount_in_try("300", "USD", "0")

    def test_rate_is_not_looked_up_again(self):
        self.assertEqual(sale_amount_in_try("300", "USD", "45"), Decimal("13500.00"))
