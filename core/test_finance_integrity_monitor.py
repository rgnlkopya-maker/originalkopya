"""Tests for on-error finance notifications; no daily digest."""
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse

from .finance_integrity_monitor import (
    STATE_KEY, audit_financial_order, process_finance_integrity,
)
from .models import CustomerMonitorState


def at(day=11, hour=12, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=ZoneInfo("Europe/Istanbul"))


def sample_order(*, sale=Decimal("18000"), cost=Decimal("11000"), currency="TRY",
                 usd_rate=None, profit=Decimal("7000"), events=None):
    snapshot = SimpleNamespace(
        satis_tl=sale, toplam_maliyet_tl=cost,
        gerceklesen_kar_tl=profit, usd_try=usd_rate,
    )
    return SimpleNamespace(
        pk=712, siparis_numarasi="SERI0323", musteri_id=1,
        musteri=SimpleNamespace(ad="MODA ZEHRADA"),
        urun_kodu="8091 TESETTÜR", satis_fiyati=sale,
        para_birimi=currency, shipment_financial_snapshot=snapshot,
        _finance_events_prefetched=events or [],
    )


def issue(key, number="SERI0323"):
    return {
        key: {
            "order_id": 712, "order_number": number, "customer": "MODA ZEHRADA",
            "product": "8091 TESETTÜR", "detail": "Maliyet eksik.",
            "type": "cost_missing",
        }
    }


class FinanceIntegrityTests(TestCase):
    @patch("core.manager_notification_signals.notify_management")
    @patch("core.finance_integrity_monitor.detect_finance_errors")
    def test_alert_only_on_new_issue_and_repeat_after_resolution(self, detected, notify):
        detected.return_value = issue("712:cost_missing")
        result = process_finance_integrity(at())
        self.assertEqual(result["new_notifications"], 1)
        self.assertEqual(result["open_issues"], 1)
        self.assertEqual(notify.call_count, 1)
        title, message, link = notify.call_args.args
        self.assertEqual(title, "Sevkiyat Finans Veri Hatası")
        self.assertIn("SERI0323", message)
        self.assertIn("MODA ZEHRADA", message)
        self.assertEqual(link, reverse("order_finance_movements", args=[712]))

        self.assertEqual(process_finance_integrity(at(minute=3))["skipped"], "within_5_minutes")
        self.assertEqual(process_finance_integrity(at(minute=6))["new_notifications"], 0)
        self.assertEqual(notify.call_count, 1)

        detected.return_value = {}
        resolved = process_finance_integrity(at(minute=12))
        self.assertEqual(resolved["open_issues"], 0)
        self.assertEqual(resolved["new_notifications"], 0)
        self.assertEqual(CustomerMonitorState.objects.get(key=STATE_KEY).payload["active"], [])

        detected.return_value = issue("712:cost_missing")
        second = process_finance_integrity(at(minute=18))
        self.assertEqual(second["new_notifications"], 1)
        self.assertEqual(notify.call_count, 2)

    @patch("core.manager_notification_signals.notify_management")
    @patch("core.finance_integrity_monitor.detect_finance_errors")
    def test_no_notifications_when_all_financial_data_is_healthy(self, detected, notify):
        detected.return_value = {}
        result = process_finance_integrity(at())
        self.assertEqual(result["open_issues"], 0)
        notify.assert_not_called()
        self.assertFalse(
            CustomerMonitorState.objects.get(key=STATE_KEY).payload["active"]
        )

    @patch("core.manager_notification_signals.notify_management")
    @patch("core.finance_integrity_monitor.detect_finance_errors")
    def test_failure_during_sending_does_not_mark_as_announced(self, detected, notify):
        detected.return_value = issue("712:cost_missing")
        notify.side_effect = RuntimeError("notification error")
        with self.assertRaises(RuntimeError):
            process_finance_integrity(at())
        self.assertFalse(CustomerMonitorState.objects.filter(key=STATE_KEY).exists())
        notify.side_effect = None
        self.assertEqual(process_finance_integrity(at())["new_notifications"], 1)

    @patch("core.finance_integrity_monitor.calculate_finance_result")
    def test_missing_cost_is_found_without_trusting_computed_profit(self, calculate):
        order = sample_order(cost=None, profit=None)
        calculate.return_value = {
            "is_final": True, "satis_tl": Decimal("18000"),
            "maliyet_tl": Decimal("0"), "kar_tl": Decimal("18000"),
        }
        problems = audit_financial_order(order)
        self.assertIn("712:cost_missing", problems)

    @patch("core.finance_integrity_monitor.calculate_finance_result")
    def test_zero_sale_is_review_warning_not_missing_cost(self, calculate):
        order = sample_order(sale=Decimal("0"), cost=Decimal("5000"), profit=Decimal("-5000"))
        calculate.return_value = {
            "is_final": True, "satis_tl": Decimal("0"),
            "maliyet_tl": Decimal("5000"), "kar_tl": Decimal("-5000"),
        }
        problems = audit_financial_order(order)
        self.assertIn("712:sale_zero", problems)
        self.assertNotIn("712:cost_missing", problems)
        self.assertIn("Ücretsiz sevkiyat olabilir", problems["712:sale_zero"]["detail"])

    @patch("core.finance_integrity_monitor.calculate_finance_result")
    def test_usd_conversion_and_profit_discrepancies(self, calculate):
        order = sample_order(
            sale=Decimal("5000"), cost=Decimal("2000"),
            profit=Decimal("2400"), currency="USD", usd_rate=Decimal("40"),
        )
        order.satis_fiyati = Decimal("100")
        calculate.return_value = {
            "is_final": True, "satis_tl": Decimal("5000"),
            "maliyet_tl": Decimal("2000"), "kar_tl": Decimal("3000"),
        }
        problems = audit_financial_order(order)
        self.assertIn("712:usd_conversion_mismatch", problems)
        self.assertIn("712:snapshot_profit_mismatch", problems)

    @patch("core.finance_integrity_monitor.calculate_finance_result")
    def test_bad_or_unknown_finance_events(self, calculate):
        order = sample_order(events=[
            SimpleNamespace(pk=91, stage="finans_hareketi", value="MALIYET_DUZELT", new_value='{"tl_amount":"10"}'),
            SimpleNamespace(pk=92, stage="finans_hareketi", value="EK_MALIYET", new_value='{"tl_amount":"invalid"}'),
            SimpleNamespace(pk=93, stage="finans_hareketi", value="NIHAI_MALIYET", new_value='{"tl_amount":"100"}'),
        ])
        calculate.return_value = {
            "is_final": True, "satis_tl": Decimal("18000"),
            "maliyet_tl": Decimal("11000"), "kar_tl": Decimal("7000"),
        }
        problems = audit_financial_order(order)
        self.assertIn("712:unknown_movement_91", problems)
        self.assertIn("712:invalid_movement_92", problems)
        self.assertNotIn("712:invalid_movement_93", problems)
