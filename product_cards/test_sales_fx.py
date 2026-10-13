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

    def test_exchange_rate_is_immutable_input(self):
        original_rate = Decimal("45")
        amount = Decimal("300")
        original_total = sale_amount_in_try(amount, "USD", original_rate)
        later_market_rate = Decimal("47")
        self.assertEqual(original_total, Decimal("13500.00"))
        self.assertEqual(sale_amount_in_try(amount, "USD", original_rate), original_total)
        self.assertNotEqual(sale_amount_in_try(amount, "USD", later_market_rate), original_total)

    def test_price_correction_uses_original_locked_rate(self):
        self.assertEqual(sale_amount_in_try("320", "USD", "45"), Decimal("14400.00"))

    def test_half_up_rounding(self):
        self.assertEqual(sale_amount_in_try("0.005", "TRY"), Decimal("0.01"))

    def test_unsupported_currency_is_rejected(self):
        with self.assertRaises(ValueError):
            sale_amount_in_try("100", "CHF", "50")

    def test_non_numeric_rate_is_rejected(self):
        with self.assertRaises(ValueError):
            sale_amount_in_try("100", "EUR", "abc")

    def test_nan_rate_is_rejected(self):
        with self.assertRaises(ValueError):
            sale_amount_in_try("100", "GBP", "NaN")
