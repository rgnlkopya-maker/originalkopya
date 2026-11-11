from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse

from .customer_monitor_service import process_customer_monitor
from .models import CustomerMonitorState, Musteri


def at_local(year, month, day, hour):
    return datetime(year, month, day, hour, 0, tzinfo=ZoneInfo("Europe/Istanbul"))


def shipped(customer, on_date, quantity, profit, revenue):
    return {
        "order": SimpleNamespace(musteri_id=customer.pk, adet=quantity),
        "ship_date": on_date,
        "result": {
            "is_final": True,
            "kar_tl": Decimal(str(profit)),
            "satis_tl": Decimal(str(revenue)),
        },
    }


class CustomerMonitorTests(TestCase):
    def setUp(self):
        self.a = Musteri.objects.create(ad="A Müşterisi")
        self.b = Musteri.objects.create(ad="B Müşterisi")

    @patch("core.manager_notification_signals.notify_management")
    @patch("core.customer_report_views._shipment_finance_rows")
    def test_status_transition_notifies_once_and_opens_customer_detail(self, rows, notify):
        last_shipped = date(2026, 8, 13)  # 90 days before November 11.
        rows.return_value = [shipped(self.a, last_shipped, 1, 100, 200)]
        first = process_customer_monitor(at_local(2026, 11, 11, 9))
        self.assertTrue(first["statuses"]["baseline"])
        notify.assert_not_called()

        second = process_customer_monitor(at_local(2026, 11, 12, 9))
        self.assertEqual(second["statuses"]["sent"], 1)
        title, message, url = notify.call_args.args
        self.assertEqual(title, "Müşteri Durumu Değişti")
        self.assertIn("AKTİF", message)
        self.assertIn("DİKKAT", message)
        self.assertIn("91 gün", message)
        self.assertEqual(url, reverse("customer_comparison_report"))

        again = process_customer_monitor(at_local(2026, 11, 12, 10))
        self.assertEqual(again["statuses"]["sent"], 0) if "statuses" in again else self.assertIn("skipped", again)
        self.assertEqual(notify.call_count, 1)

    @patch("core.manager_notification_signals.notify_management")
    @patch("core.customer_report_views._shipment_finance_rows")
    def test_all_six_leader_changes_open_customer_comparison_report(self, rows, notify):
        rows.return_value = [
            shipped(self.a, date(2026, 11, 10), 10, 1200, 10000),
            shipped(self.b, date(2026, 11, 10), 3, 700, 7000),
        ]
        first = process_customer_monitor(at_local(2026, 11, 11, 20))
        self.assertTrue(first["leaders"]["baseline"])
        notify.assert_not_called()

        rows.return_value = [
            shipped(self.a, date(2026, 11, 11), 10, 1200, 10000),
            shipped(self.b, date(2026, 11, 11), 15, 2100, 14000),
        ]
        second = process_customer_monitor(at_local(2026, 11, 12, 20))
        self.assertEqual(second["leaders"]["sent"], 6)
        self.assertEqual(notify.call_count, 6)
        titles = {call.args[0] for call in notify.call_args_list}
        self.assertEqual(titles, {
            "En Kârlı Müşteri Değişti",
            "En Fazla Adet Alan Müşteri Değişti",
            "En Yüksek Ciroya Sahip Müşteri Değişti",
            "En Düşük Kârlı Müşteri Değişti",
            "En Az Adet Alan Müşteri Değişti",
            "En Düşük Ciroya Sahip Müşteri Değişti",
        })
        for call in notify.call_args_list:
            self.assertEqual(
                call.args[2], reverse("customer_comparison_report")
            )
            expected_customer = (
                self.a if "Düşük" in call.args[0] or "Az Adet" in call.args[0]
                else self.b
            )
            self.assertIn(expected_customer.ad, call.args[1])

        process_customer_monitor(at_local(2026, 11, 12, 21))
        self.assertEqual(notify.call_count, 6)

    @patch("core.manager_notification_signals.notify_management")
    @patch("core.customer_report_views._shipment_finance_rows")
    def test_same_leader_with_new_financial_values_does_not_notify(self, rows, notify):
        rows.return_value = [shipped(self.a, date(2026, 11, 10), 2, 100, 200)]
        process_customer_monitor(at_local(2026, 11, 11, 20))
        rows.return_value = [shipped(self.a, date(2026, 11, 11), 4, 500, 900)]
        result = process_customer_monitor(at_local(2026, 11, 12, 20))
        self.assertEqual(result["leaders"]["sent"], 0)
        notify.assert_not_called()
        self.assertEqual(CustomerMonitorState.objects.count(), 2)

    @patch("core.manager_notification_signals.notify_management")
    @patch("core.customer_report_views._shipment_finance_rows")
    def test_new_lowest_rankings_get_baseline_without_false_alert(self, rows, notify):
        """Older DB snapshots contain only three high-ranking metrics."""
        rows.return_value = [
            shipped(self.a, date(2026, 11, 10), 10, 1200, 10000),
            shipped(self.b, date(2026, 11, 10), 3, 700, 7000),
        ]
        CustomerMonitorState.objects.create(
            key="customer_leaders",
            last_checked_on=date(2026, 11, 11),
            payload={
                "profit": {"id": self.a.pk, "name": self.a.ad, "value": "1200"},
                "quantity": {"id": self.a.pk, "name": self.a.ad, "value": "10"},
                "revenue": {"id": self.a.pk, "name": self.a.ad, "value": "10000"},
            },
        )
        run = process_customer_monitor(at_local(2026, 11, 12, 20))
        self.assertEqual(run["leaders"]["sent"], 0)
        notify.assert_not_called()
        snapshot = CustomerMonitorState.objects.get(key="customer_leaders").payload
        self.assertEqual(snapshot["profit_min"]["id"], self.b.pk)
        self.assertEqual(snapshot["quantity_min"]["id"], self.b.pk)
        self.assertEqual(snapshot["revenue_min"]["id"], self.b.pk)

    def test_historical_customer_notifications_open_report_not_detail(self):
        from .notification_inbox import destination_for

        report = reverse("customer_comparison_report")
        old_customer_detail = reverse("customer_detail_report", args=[self.a.pk])
        for title in (
            "Müşteri Durumu Değişti",
            "En Kârlı Müşteri Değişti",
            "En Fazla Adet Alan Müşteri Değişti",
            "En Yüksek Ciroya Sahip Müşteri Değişti",
            "En Düşük Kârlı Müşteri Değişti",
            "En Az Adet Alan Müşteri Değişti",
            "En Düşük Ciroya Sahip Müşteri Değişti",
        ):
            item = SimpleNamespace(
                order_id=None, destination_url=old_customer_detail, title=title,
            )
            self.assertEqual(destination_for(item), report)

        unrelated = SimpleNamespace(
            order_id=None, destination_url="//malicious.example",
            title="Other notice",
        )
        self.assertEqual(destination_for(unrelated), "")
