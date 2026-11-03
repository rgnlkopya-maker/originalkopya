"""Database-free checks for manager notification channel preferences."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from core.notification_preferences import (
    event_delivery, validated_choices, EVENTS_BY_KEY, EVENT_TITLE_KEYS,
)
from core.manager_notification_signals import notify_management


class NotificationPreferenceTests(SimpleTestCase):
    def test_critical_in_app_cannot_be_disabled(self):
        for key in ("invoice_failure", "backup_failed", "security_lock"):
            self.assertTrue(event_delivery({key: {"in_app": False, "push": False}}, key)[0])

    def test_optional_delivery_can_be_disabled_by_channel(self):
        self.assertEqual(
            event_delivery({"material_missing": {"in_app": False, "push": True}}, "material_missing"),
            (False, True),
        )
        self.assertEqual(
            event_delivery({"order_update": {"in_app": True, "push": False}}, "order_update"),
            (True, False),
        )

    def test_unfamiliar_event_fails_open(self):
        self.assertEqual(event_delivery({}, "unexpected_event"), (True, True))

    def test_form_never_allows_critical_in_app_opt_out(self):
        data = validated_choices({"invoice_failure_push": "on", "material_missing_push": "on"})
        self.assertTrue(data["invoice_failure"]["in_app"])
        self.assertFalse(data["backup_failed"]["push"])
        self.assertFalse(data["material_missing"]["in_app"])
        self.assertTrue(data["material_missing"]["push"])
        self.assertEqual(set(data), set(EVENTS_BY_KEY))

    @patch("core.notification_preferences.settings_for_recipients")
    @patch("core.manager_notification_signals.transaction.on_commit")
    @patch("core.manager_notification_signals.Notification.objects.create")
    @patch("core.manager_notification_signals.management_users")
    def test_manager_dispatch_respects_per_user_channels(self, managers, create, on_commit, prefs):
        managers.return_value = [SimpleNamespace(pk=5), SimpleNamespace(pk=6)]
        prefs.return_value = {
            5: {"material_missing": {"in_app": False, "push": True}},
            6: {"material_missing": {"in_app": True, "push": False}},
        }
        create.return_value.pk = 90
        notify_management("Malzeme Eksikliği", "Test", "/order/1/")
        self.assertEqual(create.call_count, 1)
        self.assertEqual(create.call_args.kwargs["user"].pk, 6)
        self.assertEqual(on_commit.call_count, 1)

    @patch("core.notification_preferences.settings_for_recipients")
    @patch("core.manager_notification_signals.transaction.on_commit")
    @patch("core.manager_notification_signals.Notification.objects.create")
    @patch("core.manager_notification_signals.management_users")
    def test_critical_alert_still_in_inbox_when_push_disabled(self, managers, create, on_commit, prefs):
        managers.return_value = [SimpleNamespace(pk=5)]
        prefs.return_value = {5: {"invoice_failure": {"in_app": False, "push": False}}}
        notify_management("Fatura Aktarım Hatası", "FT 5", "/")
        create.assert_called_once()
        on_commit.assert_not_called()
