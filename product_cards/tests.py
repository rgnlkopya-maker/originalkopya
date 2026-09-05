import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from core.models import Musteri, Order, OrderEvent, ProductCost
from .finance_views import calculate_finance_result
from .models import ExchangeRate, OrderFinancialSnapshot, ShipmentFinancialSnapshot


class FinanceSnapshotRegressionTests(TestCase):
    def setUp(self):
        ExchangeRate.objects.create(rate_date="2026-09-05", usd_try=Decimal("48.319500"))
        ProductCost.objects.create(
            urun_kodu="7165",
            maliyet=Decimal("9253.52"),
            para_birimi="TRY",
            is_active=True,
        )

    def _create_order(self, **kwargs):
        defaults = {
            "siparis_tipi": "SERI",
            "urun_kodu": "7165",
            "satis_fiyati": Decimal("13000.00"),
            "para_birimi": "TRY",
            "maliyet_para_birimi": "TRY",
        }
        defaults.update(kwargs)
        with patch("core.signals_qr.ensure_order_qr"):
            return Order.objects.create(**defaults)

    def test_order_snapshot_uses_active_product_cost_when_order_cost_is_zero(self):
        order = self._create_order(maliyet_uygulanan=Decimal("0"))
        order.refresh_from_db()
        snapshot = OrderFinancialSnapshot.objects.get(order=order)

        self.assertEqual(order.maliyet_uygulanan, Decimal("9253.52"))
        self.assertEqual(snapshot.satis_tl, Decimal("13000.00"))
        self.assertEqual(snapshot.maliyet_tl, Decimal("9253.52"))
        self.assertEqual(snapshot.beklenen_kar_tl, Decimal("3746.48"))
        self.assertEqual(snapshot.beklenen_kar_orani, Decimal("28.82"))

    def test_incomplete_snapshot_repairs_when_sale_price_is_saved_after_creation(self):
        order = self._create_order(satis_fiyati=Decimal("0"), maliyet_uygulanan=Decimal("0"))
        snapshot = OrderFinancialSnapshot.objects.get(order=order)
        self.assertEqual(snapshot.satis_tl, Decimal("0.00"))

        order.satis_fiyati = Decimal("13000.00")
        order.save(update_fields=["satis_fiyati"])
        snapshot.refresh_from_db()

        self.assertEqual(snapshot.satis_tl, Decimal("13000.00"))
        self.assertEqual(snapshot.maliyet_tl, Decimal("9253.52"))
        self.assertEqual(snapshot.beklenen_kar_tl, Decimal("3746.48"))
        self.assertEqual(snapshot.beklenen_kar_orani, Decimal("28.82"))

    def test_shipment_snapshot_uses_current_sale_and_active_product_cost(self):
        order = self._create_order(maliyet_uygulanan=Decimal("0"))
        OrderEvent.objects.create(
            order=order,
            user="test",
            stage="sevkiyat_durum",
            value="gonderildi",
        )

        snapshot = ShipmentFinancialSnapshot.objects.get(order=order)
        self.assertEqual(snapshot.satis_tl, Decimal("13000.00"))
        self.assertEqual(snapshot.urun_maliyeti_tl, Decimal("9253.52"))
        self.assertEqual(snapshot.toplam_maliyet_tl, Decimal("9253.52"))
        self.assertEqual(snapshot.gerceklesen_kar_tl, Decimal("3746.48"))
        self.assertEqual(snapshot.gerceklesen_kar_orani, Decimal("28.82"))

    def test_shipment_finance_discount_and_extra_cost_are_calculated_without_changing_shipping_status(self):
        order = self._create_order(maliyet_uygulanan=Decimal("0"))
        OrderEvent.objects.create(order=order, user="test", stage="sevkiyat_durum", value="gonderildi")
        OrderEvent.objects.create(
            order=order,
            user="manager",
            stage="finans_hareketi",
            value="INDIRIM",
            event_type="order_update",
            new_value=json.dumps({"tl_amount": "1000.00"}),
        )
        OrderEvent.objects.create(
            order=order,
            user="manager",
            stage="finans_hareketi",
            value="EK_MALIYET",
            event_type="order_update",
            new_value=json.dumps({"tl_amount": "500.00"}),
        )

        result = calculate_finance_result(order)
        self.assertEqual(result["status"], "SEVKEDILDI")
        self.assertTrue(result["is_final"])
        self.assertEqual(result["satis_tl"], Decimal("12000.00"))
        self.assertEqual(result["maliyet_tl"], Decimal("9753.52"))
        self.assertEqual(result["kar_tl"], Decimal("2246.48"))
        self.assertEqual(result["kar_orani"], Decimal("18.72"))
        self.assertEqual(len(result["movements"]), 2)

    def test_return_then_reship_restores_sale_and_keeps_prior_discount(self):
        order = self._create_order(maliyet_uygulanan=Decimal("0"))
        OrderEvent.objects.create(order=order, user="test", stage="sevkiyat_durum", value="gonderildi")
        OrderEvent.objects.create(
            order=order,
            user="manager",
            stage="finans_hareketi",
            value="INDIRIM",
            event_type="order_update",
            new_value=json.dumps({"tl_amount": "1000.00"}),
        )
        OrderEvent.objects.create(order=order, user="test", stage="sevkiyat_durum", value="iade_geldi")

        returned = calculate_finance_result(order)
        self.assertEqual(returned["status"], "IADE")
        self.assertEqual(returned["satis_tl"], Decimal("0.00"))

        OrderEvent.objects.create(order=order, user="test", stage="sevkiyat_durum", value="gonderildi")
        resent = calculate_finance_result(order)
        self.assertEqual(resent["status"], "SEVKEDILDI")
        self.assertEqual(resent["satis_tl"], Decimal("12000.00"))
        self.assertEqual(resent["kar_tl"], Decimal("2746.48"))


class MultiOrderFinancePostTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("finance-manager", password="test")
        patron, _ = Group.objects.get_or_create(name="patron")
        self.user.groups.add(patron)
        self.client.force_login(self.user)
        self.customer = Musteri.objects.create(ad="Finans Test Müşteri")
        ExchangeRate.objects.create(rate_date="2026-09-05", usd_try=Decimal("48.319500"))
        ProductCost.objects.create(
            urun_kodu="7165",
            maliyet=Decimal("9253.52"),
            para_birimi="TRY",
            is_active=True,
        )

    @patch("core.signals_qr.ensure_order_qr")
    def test_multi_order_post_preserves_sale_price_and_builds_profit_snapshot(self, _qr):
        response = self.client.post(
            "/orders/multi-create/",
            {
                "siparis_tipi": "SERI",
                "musteri": str(self.customer.pk),
                "urun_kodu": "7165",
                "urun_tipi": "BALIK",
                "renk_row_0": "TAŞ",
                "beden_row_0[]": ["38"],
                "adet_row_0": "1",
                "musteri_ref_row_0": "",
                "teslim_tarihi": "",
                "aciklama": "",
                "satis_fiyati": "13000.00",
                "para_birimi": "TRY",
                "maliyet_uygulanan": "",
                "maliyet_para_birimi": "TRY",
            },
        )

        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(urun_kodu="7165")
        order.refresh_from_db()
        snapshot = OrderFinancialSnapshot.objects.get(order=order)

        self.assertEqual(order.satis_fiyati, Decimal("13000.00"))
        self.assertEqual(order.maliyet_uygulanan, Decimal("9253.52"))
        self.assertEqual(snapshot.satis_tl, Decimal("13000.00"))
        self.assertEqual(snapshot.maliyet_tl, Decimal("9253.52"))
        self.assertEqual(snapshot.beklenen_kar_tl, Decimal("3746.48"))
