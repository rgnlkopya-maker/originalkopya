"""Safeguards for daily 20:00 product leaderboard notifications."""
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse

from .models import CustomerMonitorState
from .product_monitor_service import (
    RANKINGS, _display_amount, collect_product_rankings, process_product_monitor,
)


def local_time(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=ZoneInfo("Europe/Istanbul"))


def shipped(code, quantity, revenue, cost, profit, *, missing_cost=False):
    order = SimpleNamespace(
        urun_kodu=code, urun_tipi="BALIK", adet=quantity,
        musteri_id=17, musteri=SimpleNamespace(ad="Örnek Müşteri"),
        renk="KIRMIZI", siparis_tipi="SERI",
    )
    return {
        "order": order,
        "ship_date": date(2026, 11, 11),
        "result": {
            "is_final": True,
            "snapshot": SimpleNamespace(
                toplam_maliyet_tl=None if missing_cost else Decimal(str(cost))
            ),
            "satis_tl": Decimal(str(revenue)),
            "maliyet_tl": Decimal(str(cost)),
            "kar_tl": Decimal(str(profit)),
        },
    }


class ProductMonitorTests(TestCase):
    @patch("core.manager_notification_signals.notify_management")
    @patch("core.customer_report_views._shipment_finance_rows")
    def test_only_after_20_first_run_is_baseline_and_all_eight_changes_send(self, rows, notify):
        rows.return_value = [
            shipped("A 7119", 10, 10000, 7000, 3000),
            shipped("B 8020", 2, 2000, 1000, 1000),
        ]
        before = process_product_monitor(local_time(11, 19, 59))
        self.assertEqual(before["skipped"], "before_20")
        rows.assert_not_called()
        notify.assert_not_called()

        baseline = process_product_monitor(local_time(11, 20))
        self.assertTrue(baseline["baseline"])
        self.assertEqual(baseline["sent"], 0)
        notify.assert_not_called()

        rows.return_value = [
            shipped("A 7119", 2, 2000, 1000, 1000),
            shipped("B 8020", 12, 12000, 8000, 4000),
        ]
        next_day = process_product_monitor(local_time(12, 20))
        self.assertEqual(next_day["sent"], 8)
        self.assertEqual(notify.call_count, 8)
        self.assertEqual(
            {c.args[0] for c in notify.call_args_list},
            {parts[2] for parts in RANKINGS.values()},
        )
        target = reverse("product_performance_report")
        for notification in notify.call_args_list:
            title, body, destination = notification.args
            self.assertEqual(destination, target)
            self.assertIn("Önceki ürün:", body)
            self.assertIn("Yeni ürün:", body)
            self.assertIn("Ürün Performans Raporu", body)
            if "Düşük" in title or "Az Sevk" in title:
                self.assertIn("A 7119", body.split("Yeni ürün:", 1)[1])
            else:
                self.assertIn("B 8020", body.split("Yeni ürün:", 1)[1])

        same_day = process_product_monitor(local_time(12, 20, 30))
        self.assertEqual(same_day["skipped"], "already_checked")
        self.assertEqual(notify.call_count, 8)
        self.assertEqual(
            CustomerMonitorState.objects.get(key="product_leaders").last_checked_on,
            date(2026, 11, 12),
        )

    @patch("core.manager_notification_signals.notify_management")
    @patch("core.customer_report_views._shipment_finance_rows")
    def test_value_changes_without_ranking_changes_do_not_notify(self, rows, notify):
        rows.return_value = [
            shipped("A", 10, 10000, 7000, 3000),
            shipped("B", 2, 2000, 1000, 1000),
        ]
        process_product_monitor(local_time(11, 20))
        rows.return_value = [
            shipped("A", 11, 11000, 8000, 3000),
            shipped("B", 3, 3000, 1200, 1800),
        ]
        result = process_product_monitor(local_time(12, 20))
        self.assertEqual(result["sent"], 0)
        notify.assert_not_called()

    def test_ties_use_stable_product_code_not_row_order(self):
        rows = [
            shipped("  b ", 1, 1000, 500, 500),
            shipped(" A ", 1, 1000, 500, 500),
        ]
        one = collect_product_rankings(rows)
        two = collect_product_rankings(list(reversed(rows)))
        self.assertEqual(one, two)
        for field in RANKINGS:
            self.assertEqual(one[field]["code"], "A")

    @patch("core.manager_notification_signals.notify_management")
    @patch("core.customer_report_views._shipment_finance_rows")
    def test_no_data_does_not_erase_saved_leaders(self, rows, notify):
        rows.return_value = []
        result = process_product_monitor(local_time(11, 20))
        self.assertEqual(result["skipped"], "no_shipped_products")
        self.assertFalse(CustomerMonitorState.objects.filter(key="product_leaders").exists())
        notify.assert_not_called()

    @patch("core.manager_notification_signals.notify_management")
    @patch("core.customer_report_views._shipment_finance_rows")
    def test_cost_warning_and_negative_profit_ranking(self, rows, notify):
        rows.return_value = [
            shipped("A", 2, 1000, 1400, -400),
            shipped("B", 1, 500, 0, 500, missing_cost=True),
        ]
        first = collect_product_rankings(rows.return_value)
        self.assertEqual(first["profit_min"]["code"], "A")
        self.assertEqual(first["cost_min"]["code"], "B")
        self.assertEqual(first["cost_min"]["missing_cost"], 1)
        process_product_monitor(local_time(11, 20))
        rows.return_value = [
            shipped("A", 2, 1000, 1400, -400),
            shipped("B", 1, 500, 0, 500, missing_cost=False),
            shipped("C", 1, 200, 0, 200, missing_cost=True),
        ]
        process_product_monitor(local_time(12, 20))
        messages = [c.args[1] for c in notify.call_args_list]
        self.assertTrue(any("maliyet kaydı eksik" in m for m in messages))

    def test_turkish_amount_format(self):
        self.assertEqual(_display_amount("1234567.8", "TL"), "1.234.567,80 TL")
        self.assertEqual(_display_amount("15", "adet"), "15 adet")
