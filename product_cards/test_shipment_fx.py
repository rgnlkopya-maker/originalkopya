from datetime import date, datetime, timezone
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Order, OrderEvent
from .finance_views import calculate_finance_result, prepare_shipment_report_sale
from .models import ExchangeRate, ShipmentFinancialSnapshot
from .showroom_transfer_views import suspend_order_qr


class ShipmentFxTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser("shipping-fx")
        ExchangeRate.objects.create(rate_date=date(2026, 11, 6), usd_try=D("50"), eur_try=D("55"), gbp_try=D("65"))
        ExchangeRate.objects.create(rate_date=date(2026, 11, 9), usd_try=D("52"), eur_try=D("1"), gbp_try=D("67"))
        ExchangeRate.objects.create(rate_date=date(2026, 11, 10), usd_try=D("60"), eur_try=D("70"), gbp_try=D("80"))

    def order(self, currency, nominal="100"):
        with suspend_order_qr():
            return Order.objects.create(
                urun_kodu="FX TEST", siparis_tipi="OZEL", satis_fiyati=D(nominal),
                para_birimi=currency, maliyet_override=D("1000"),
            )

    def event(self, order, timestamp, *, legacy=False):
        row = OrderEvent(order=order, user="test", stage="sevkiyat_durum", value="gonderildi", timestamp=timestamp)
        if legacy:
            OrderEvent.objects.bulk_create([row])
        else:
            row.save()

    def test_new_shipment_locks_rates_using_istanbul_date_and_missing_currency_fallback(self):
        timestamp = datetime(2026, 11, 8, 22, tzinfo=timezone.utc)  # 9 Nov in Türkiye
        for currency, revenue in (("USD", "5200"), ("EUR", "5500"), ("GBP", "6700"), ("TRY","100")):
            with self.subTest(currency=currency):
                order = self.order(currency)
                self.event(order, timestamp)
                snapshot = ShipmentFinancialSnapshot.objects.get(order=order)
                self.assertEqual(snapshot.fx_reference_date, date(2026, 11, 9))
                self.assertEqual(snapshot.satis_tl, D(revenue))
                self.assertEqual(snapshot.toplam_maliyet_tl, D("1000"))

    def test_later_price_edit_keeps_locked_shipment_rate_and_cost(self):
        order = self.order("EUR")
        self.event(order, datetime(2026, 11, 6, 12, tzinfo=timezone.utc))
        ExchangeRate.objects.filter(rate_date=date(2026, 11, 6)).update(eur_try=D("56"))
        order.satis_fiyati = D("200")
        order.save(update_fields=["satis_fiyati"])
        snapshot = ShipmentFinancialSnapshot.objects.get(order=order)
        self.assertEqual(snapshot.satis_tl, D("11000"))
        self.assertEqual(snapshot.gerceklesen_kar_tl, D("10000"))

    def test_old_report_uses_first_sevkiyat_rate_keeps_stored_snapshot(self):
        order = self.order("EUR")
        self.event(order, datetime(2026, 11, 6, 12, tzinfo=timezone.utc), legacy=True)
        self.event(order, datetime(2026, 11, 10, 12, tzinfo=timezone.utc), legacy=True)
        snapshot = ShipmentFinancialSnapshot.objects.create(
            order=order, satis_para_birimi="EUR", satis_fiyati=D("100"),
            satis_tl=D("100"), toplam_maliyet_tl=D("1000"),
        )
        prepare_shipment_report_sale(order)
        result = calculate_finance_result(order)
        self.assertEqual(result["satis_tl"], D("5500"))
        self.assertEqual(result["kar_tl"], D("4500"))
        self.assertEqual(result["kar_orani"], D("81.82"))
        self.client.force_login(self.user)
        response = self.client.get(reverse("sevkiyat_finans_tablosu"), {"siparis_no": order.siparis_numarasi})
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.content.decode(), r'data-sale="5500[.,]00"')
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.satis_tl, D("100"))

    def test_missing_historical_rate_is_not_replaced_by_future_rate(self):
        order = self.order("GBP")
        self.event(order, datetime(2026, 10, 30, 12, tzinfo=timezone.utc))
        order.refresh_from_db()
        prepare_shipment_report_sale(order)
        result = calculate_finance_result(order)
        self.assertIsNone(result["sevk_satis_tl"])
        self.assertTrue(result["missing_sale"])
