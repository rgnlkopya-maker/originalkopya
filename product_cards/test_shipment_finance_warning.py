"""Regression tests for the red warning on shipment finance rows."""
import json
import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Order, OrderEvent
from .finance_views import calculate_finance_result
from .models import ShipmentFinancialSnapshot
from .showroom_transfer_views import suspend_order_qr


class ShipmentFinanceWarningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser("shipment-test", password="test")

    def order(self, *, sale="9250", cost="0", snapshot=True):
        with suspend_order_qr():
            order = Order.objects.create(urun_kodu="8005 TEST", siparis_tipi="OZEL", adet=1)
        # Preserve exact fixture values rather than run today's rates and cost signals.
        OrderEvent.objects.bulk_create([
            OrderEvent(order=order, user="test", stage="sevkiyat_durum", value="gonderildi")
        ])
        if snapshot:
            ShipmentFinancialSnapshot.objects.create(order=order, satis_tl=sale, toplam_maliyet_tl=cost)
        return order

    def movement(self, order, kind, tl_amount, amount=None, currency="TRY"):
        OrderEvent.objects.create(
            order=order, user="test", stage="finans_hareketi", value=kind,
            event_type="order_update",
            new_value=json.dumps({"tl_amount": tl_amount, "amount": amount, "currency": currency}),
        )

    def row(self, order):
        self.client.force_login(self.user)
        response = self.client.get(reverse("sevkiyat_finans_tablosu"), {"siparis_no": order.siparis_numarasi})
        self.assertEqual(response.status_code, 200)
        rows = re.findall(r'<tr class="finance-row[^>]*>.*?</tr>', response.content.decode(), re.S)
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_final_cost_clears_warning_without_rewriting_original_shipment(self):
        order = self.order()
        self.assertIn('title="Eksik finans bilgisi: maliyet."', self.row(order))
        self.movement(order, "NIHAI_MALIYET", "9000.00", "9000")
        row = self.row(order)
        self.assertNotIn("ship-finance-missing", row)
        self.assertRegex(row, r'data-cost="9000[.,]00"')
        snap = ShipmentFinancialSnapshot.objects.get(order=order)
        self.assertEqual(snap.toplam_maliyet_tl, Decimal("0"))

    def test_missing_sale_stays_red_after_final_cost(self):
        order = self.order(sale=None, cost=None)
        self.movement(order, "NIHAI_MALIYET", "8000.00")
        self.assertIn('title="Eksik finans bilgisi: satış fiyatı."', self.row(order))
        self.movement(order, "FIYAT_DUZELT", "15000.00")
        self.assertNotIn("ship-finance-missing", self.row(order))

    def test_extra_cost_alone_does_not_fill_missing_base_cost(self):
        order = self.order(cost=None)
        self.movement(order, "EK_MALIYET", "500.00", "500")
        self.assertIn('title="Eksik finans bilgisi: maliyet."', self.row(order))

    def test_explicit_zero_is_valid_but_unconverted_amount_is_missing(self):
        order = self.order(cost=None)
        self.movement(order, "NIHAI_MALIYET", "0.00", "100", currency="USD")
        self.assertTrue(calculate_finance_result(order)["missing_cost"])
        self.movement(order, "NIHAI_MALIYET", "0.00", "0")
        result = calculate_finance_result(order)
        self.assertFalse(result["missing_cost"])
        self.assertEqual(result["maliyet_tl"], 0)

    def test_known_sale_reduced_to_zero_is_not_missing(self):
        order = self.order(cost="8000")
        self.movement(order, "INDIRIM", "9250.00", "9250")
        result = calculate_finance_result(order)
        self.assertFalse(result["missing_sale"])
        self.assertEqual(result["satis_tl"], 0)
        self.assertNotIn("ship-finance-missing", self.row(order))

    def test_shipment_without_finance_record_is_still_marked(self):
        order = self.order(snapshot=False)
        self.assertIn('title="Eksik finans bilgisi: satış fiyatı ve maliyet."', self.row(order))
