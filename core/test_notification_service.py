"""No ordinary order edit is allowed to publish a notification."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase

from core.notification_service import publish_order_update


class DisabledOrderUpdateNotificationTests(SimpleTestCase):
    def test_order_edit_publisher_is_inert_even_with_changed_fields(self):
        with patch("core.models.Notification.objects.bulk_create") as create:
            count = publish_order_update(
                order=SimpleNamespace(pk=7, siparis_numarasi="SERI0368"),
                changed_fields=["aciklama", "teslim_tarihi"],
                actor=SimpleNamespace(username="mehmet"),
            )
            self.assertEqual(count, 0)
            create.assert_not_called()

    def test_order_edit_view_does_not_call_legacy_publisher(self):
        source = (Path(settings.BASE_DIR) / "core/views.py").read_text(encoding="utf-8")
        self.assertNotIn("publish_order_update(", source)
        self.assertIn('event_type="order_update"', source)

    def test_catalog_has_no_order_edit_notification(self):
        from core.notification_center_views import EVENT_CATALOG
        from core.notification_preferences import EVENTS
        self.assertNotIn("order_update", [item[0] for item in EVENTS])
        self.assertFalse(any("Sipariş bilgisi güncellendi" in row[0] for row in EVENT_CATALOG))
