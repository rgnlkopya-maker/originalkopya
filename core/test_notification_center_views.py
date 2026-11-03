"""Isolated regression tests for the management notification center."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.template import engines
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse
from django.utils import timezone

from core.notification_center_views import notification_center


class NotificationCenterTests(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.manager = SimpleNamespace(
            is_authenticated=True, is_active=True, pk=9,
        )
        self.preference_patch = patch("core.notification_center_views.settings_for_user", return_value={})
        self.preference_patch.start()
        self.addCleanup(self.preference_patch.stop)

    def test_template_compiles_and_links_are_distinct(self):
        engines["django"].get_template("core/notification_center.html")
        self.assertEqual(reverse("notification_center"), "/yonetim/bildirim-merkezi/")
        self.assertEqual(reverse("notification_list"), "/notifications/")
        self.assertEqual(resolve("/yonetim/bildirim-merkezi/").func, notification_center)

    @patch("core.notification_center_views.is_manager", return_value=False)
    def test_non_manager_cannot_view(self, permitted):
        req = self.factory.get("/yonetim/bildirim-merkezi/")
        req.user = self.manager
        response = notification_center(req)
        self.assertEqual(response.status_code, 403)

    @patch("core.notification_center_views.is_manager", return_value=True)
    @patch("core.notification_center_views.render", return_value=HttpResponse("ok"))
    @patch("core.notification_center_views.get_user_model")
    @patch("core.notification_center_views.Reminder.objects")
    @patch("core.notification_center_views.Notification.objects")
    def test_manager_get_shows_actual_catalog(self, notices, reminders, users, render, permitted):
        req = self.factory.get("/yonetim/bildirim-merkezi/")
        req.user = self.manager
        response = notification_center(req)
        self.assertEqual(response.status_code, 200)
        context = render.call_args.args[2]
        self.assertGreaterEqual(len(context["event_catalog"]), 9)
        self.assertEqual(render.call_args.args[1], "core/notification_center.html")

    @patch("core.notification_center_views.is_manager", return_value=True)
    @patch("core.notification_center_views.Reminder.objects.create")
    @patch("core.notification_center_views.get_user_model")
    def test_reminder_creation_uses_existing_model(self, users, create, permitted):
        users.return_value.objects.filter.return_value.first.return_value = SimpleNamespace(pk=9)
        due = timezone.localtime(timezone.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
        req = self.factory.post("/yonetim/bildirim-merkezi/", {
            "title": "Sevkiyat toplantısı",
            "due_at": due,
            "target_type": "user",
            "target_user": "9",
            "repeat": "weekly",
            "notify_interval_minutes": "15",
        })
        req.user = self.manager
        req.session = {}
        req._messages = __import__("django.contrib.messages.storage.fallback", fromlist=["FallbackStorage"]).FallbackStorage(req)
        response = notification_center(req)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(create.call_args.kwargs["title"], "Sevkiyat toplantısı")
        self.assertEqual(create.call_args.kwargs["repeat"], "weekly")

    @patch("core.notification_center_views.is_manager", return_value=True)
    @patch("core.notification_center_views.NotificationPreference.objects.update_or_create")
    def test_preferences_save_is_scoped_to_current_user(self, save, permitted):
        req = self.factory.post("/yonetim/bildirim-merkezi/", {
            "action": "save_preferences",
            "material_missing_push": "on",
            "invoice_failure_push": "on",
        })
        req.user = self.manager
        req.session = {}
        req._messages = __import__("django.contrib.messages.storage.fallback", fromlist=["FallbackStorage"]).FallbackStorage(req)
        result = notification_center(req)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(save.call_args.kwargs["user"], self.manager)
        choices = save.call_args.kwargs["defaults"]["choices"]
        self.assertTrue(choices["invoice_failure"]["in_app"])
        self.assertNotIn("order_update", choices)
        self.assertTrue(choices["material_missing"]["push"])

    def test_anonymous_user_is_redirected_to_login(self):
        req = self.factory.get("/yonetim/bildirim-merkezi/")
        req.user = AnonymousUser()
        response = notification_center(req)
        self.assertEqual(response.status_code, 302)
