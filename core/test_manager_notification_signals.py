"""Database-free regression checks for manager-only operation notifications."""
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from django.test import SimpleTestCase

from core.manager_notification_signals import (notify_management, notify_management_once, invoice_transfer_failure, notify_management_on_order_event, notify_management_on_backup_failure)


class ManagerOperationNotificationTests(SimpleTestCase):

    def setUp(self):
        self.preference_patch = patch("core.notification_preferences.settings_for_recipients", return_value={})
        self.preference_patch.start()
        self.addCleanup(self.preference_patch.stop)

    @patch("core.manager_notification_signals.transaction.on_commit")
    @patch("core.manager_notification_signals.Notification.objects.create")
    @patch("core.manager_notification_signals.management_users")
    def test_only_selected_manager_recipients_are_notified(self, users, create, on_commit):
        users.return_value = [SimpleNamespace(pk=1), SimpleNamespace(pk=2)]
        notify_management("Alert", "Body", "/path/", exclude_user_ids={1})
        self.assertEqual(create.call_count, 1)
        self.assertEqual(create.call_args.kwargs["user"].pk, 2)
        self.assertEqual(on_commit.call_count, 1)

    @patch("core.manager_notification_signals.notify_management")
    def test_successful_backup_never_notifies(self, notify):
        run = SimpleNamespace(completed_at="done", success=True)
        notify_management_on_backup_failure(sender=None, instance=run, created=False)
        notify.assert_not_called()

    @patch("core.manager_notification_signals.notify_management")
    def test_non_stage_events_do_not_notify(self, notify):
        event = SimpleNamespace(event_type="order_update")
        notify_management_on_order_event(sender=None, instance=event, created=True)
        notify.assert_not_called()

    @patch("core.manager_notification_signals.notify_management")
    @patch("core.manager_notification_signals.cache.add")
    def test_deduplicates_matching_critical_alerts(self, add, notify):
        add.side_effect = [True, False]
        self.assertTrue(notify_management_once("invoice", "bh:1", "Title", "Message", "/"))
        self.assertFalse(notify_management_once("invoice", "bh:1", "Title", "Message", "/"))
        notify.assert_called_once()

    @patch("core.manager_notification_signals.notify_management_once")
    def test_invoice_failure_alert_does_not_include_external_error_text(self, send):
        invoice_transfer_failure("parasut", 45)
        args = send.call_args.args
        self.assertEqual(args[2], "Fatura Aktarım Hatası")
        self.assertIn("#45", args[3])
        self.assertNotIn("token", args[3].lower())
        self.assertEqual(send.call_args.kwargs["timeout"], 600)

    @patch("core.manager_notification_signals.notify_management_once")
    @patch("core.manager_notification_signals.OrderFlag.objects.filter")
    def test_material_missing_produces_one_manager_alert(self, flags, send):
        flags.return_value.prefetch_related.return_value = []
        order = SimpleNamespace(pk=43, musteri_id=None, siparis_numarasi="S-43",
                                urun_kodu="7119", renk="Lacivert", beden="40")
        event = SimpleNamespace(order=order, event_type="stage",
                                stage="malzeme_durum", value="eksik", user="operator")
        notify_management_on_order_event(sender=None, instance=event, created=True)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args.args[2], "Malzeme Eksikliği")
        self.assertEqual(send.call_args.kwargs["timeout"], 3600)

    @patch("core.manager_notification_signals.notify_management_once")
    @patch("core.manager_notification_signals.OrderFlag.objects.filter")
    def test_material_sufficient_does_not_alert(self, flags, send):
        flags.return_value.prefetch_related.return_value = []
        order = SimpleNamespace(pk=43, musteri_id=None, siparis_numarasi="S-43",
                                urun_kodu="7119", renk="Lacivert", beden="40")
        event = SimpleNamespace(order=order, event_type="stage",
                                stage="malzeme_durum", value="kesildi", user="operator")
        notify_management_on_order_event(sender=None, instance=event, created=True)
        send.assert_not_called()
