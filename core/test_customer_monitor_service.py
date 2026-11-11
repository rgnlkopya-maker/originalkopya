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
        self.assertEqual(url, reverse("customer_detail_report", args=[self.a.pk]))

        again = process_customer_monitor(at_local(2026, 11, 12, 10))
        self.assertEqual(again["statuses"]["sent"], 0) if "statuses" in again else self.assertIn("skipped", again)
        self.assertEqual(notify.call_count, 1)

    @patch("core.manager_notification_signals.notify_management")
    @patch("core.customer_report_views._shipment_finance_rows")
    def test_all_three_leader_changes_send_distinct_customer_links(self, rows, notify):
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
        self.assertEqual(second["leaders"]["sent"], 3)
        self.assertEqual(notify.call_count, 3)
        titles = {call.args[0] for call in notify.call_args_list}
        self.assertEqual(titles, {
            "En Kârlı Müşteri Değişti",
            "En Fazla Adet Alan Müşteri Değişti",
            "En Yüksek Ciroya Sahip Müşteri Değişti",
        })
        for call in notify.call_args_list:
            self.assertIn(self.b.ad, call.args[1])
            self.assertEqual(
                call.args[2], reverse("customer_detail_report", args=[self.b.pk])
            )

        process_customer_monitor(at_local(2026, 11, 12, 21))
        self.assertEqual(notify.call_count, 3)

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

    def test_explicit_destination_overrides_generic_notification_destination(self):
        from .notification_inbox import destination_for

        target = reverse("customer_detail_report", args=[self.a.pk])
        item = SimpleNamespace(
            order_id=None, destination_url=target,
            title="Müşteri Durumu Değişti",
        )
        self.assertEqual(destination_for(item), target)
        item.destination_url = "//malicious.example"
        self.assertEqual(destination_for(item), "")
