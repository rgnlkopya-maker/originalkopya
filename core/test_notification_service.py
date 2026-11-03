"""Database-free tests for phase-one centralized notification publishing."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from core.notification_service import publish_order_update


class CentralNotificationServiceTests(SimpleTestCase):
    @patch("core.notification_service.Notification.objects.bulk_create")
    @patch("core.notification_service.management_recipients")
    def test_order_update_sends_only_to_unique_active_management_recipients(self, recipients, save):
        recipients.return_value.values_list.return_value = [11, 19]
        order = SimpleNamespace(pk=9, siparis_numarasi="SERI0368")
        actor = SimpleNamespace(username="mehmet")
        count = publish_order_update(
            order=order, changed_fields=["aciklama", "teslim_tarihi"], actor=actor
        )
        self.assertEqual(count, 2)
        notifications = save.call_args.args[0]
        self.assertEqual([n.user_id for n in notifications], [11, 19])
        self.assertTrue(all(n.order is order for n in notifications))
        self.assertTrue(all(n.title == "SERI0368 güncellendi" for n in notifications))
        self.assertTrue(all(
            n.message == "Değişen alanlar: Açıklama, Teslim Tarihi. Güncelleyen: mehmet"
            for n in notifications
        ))

    @patch("core.notification_service.Notification.objects.bulk_create")
    @patch("core.notification_service.management_recipients")
    def test_no_changed_fields_produces_no_notification(self, recipients, save):
        result = publish_order_update(
            order=SimpleNamespace(siparis_numarasi="SERI0368"),
            changed_fields=[], actor=SimpleNamespace(username="mehmet"),
        )
        self.assertEqual(result, 0)
        recipients.assert_not_called()
        save.assert_not_called()

    @patch("core.notification_service.Notification.objects.bulk_create")
    @patch("core.notification_service.management_recipients")
    def test_no_management_recipient_creates_no_record(self, recipients, save):
        recipients.return_value.values_list.return_value = []
        result = publish_order_update(
            order=SimpleNamespace(siparis_numarasi="SERI0368"),
            changed_fields=["renk"], actor=None,
        )
        self.assertEqual(result, 0)
        save.assert_not_called()

    @patch("core.notification_service.get_user_model")
    def test_management_queryset_filters_active_and_roles(self, get_user_model):
        from core.notification_service import management_recipients
        users = MagicMock()
        get_user_model.return_value.objects = users
        management_recipients()
        users.filter.assert_called_once_with(is_active=True)
        users.filter.return_value.filter.assert_called_once()
        users.filter.return_value.filter.return_value.distinct.assert_called_once()
