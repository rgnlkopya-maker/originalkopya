"""Database-free regression checks for manager-only operation notifications."""
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from django.test import SimpleTestCase

from core.manager_notification_signals import notify_management, notify_management_on_order_event, notify_management_on_backup_failure


class ManagerOperationNotificationTests(SimpleTestCase):
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
