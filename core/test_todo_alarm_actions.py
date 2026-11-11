from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .todo_models import TodoItem


class TodoAlarmActionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "todo-alarm-test", password="test"
        )
        self.client.force_login(self.user)
        self.item = TodoItem.objects.create(
            user=self.user,
            title="Alarm test",
            due_at=timezone.now() - timedelta(minutes=2),
            alarm_enabled=True,
            alarm_interval_minutes=5,
        )

    def test_snooze_popup_confirms_save_and_hides_alarm_until_due(self):
        response = self.client.post(
            reverse("todo_snooze", args=[self.item.pk]),
            {"minutes": "15"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["snoozed"])
        self.assertEqual(payload["minutes"], 15)
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.snoozed_until)
        self.assertEqual(payload["snoozed_until"], self.item.snoozed_until.isoformat())
        self.assertGreater(self.item.snoozed_until, timezone.now() + timedelta(minutes=14))
        pending = self.client.get(reverse("todo_pending_alarms")).json()
        self.assertEqual(pending["alarms"], [])

    def test_snooze_native_form_redirects_and_saves(self):
        response = self.client.post(
            reverse("todo_snooze", args=[self.item.pk]),
            {"minutes": "30"},
        )
        self.assertRedirects(response, reverse("todo_list"))
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.snoozed_until)

    def test_snooze_from_another_screen_stays_on_that_screen(self):
        source = "/uretim-asama-kontrolu/?section=unshipped"
        response = self.client.post(
            reverse("todo_snooze", args=[self.item.pk]),
            {"minutes": "10"},
            HTTP_REFERER="http://testserver" + source,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "http://testserver" + source)
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.snoozed_until)

    def test_snooze_refuses_external_redirect(self):
        response = self.client.post(
            reverse("todo_snooze", args=[self.item.pk]),
            {"minutes": "10"},
            HTTP_REFERER="https://untrusted.example/elsewhere",
        )
        self.assertRedirects(response, reverse("todo_list"))

    def test_completion_popup_confirms_save_and_does_not_reopen(self):
        url = reverse("todo_complete", args=[self.item.pk])
        for _ in range(2):
            response = self.client.post(
                url, {"action": "finish"},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"ok": True, "completed": True})
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.completed_at)
        self.assertEqual(
            self.client.get(reverse("todo_pending_alarms")).json()["alarms"], []
        )

    def test_snooze_cannot_update_someone_elses_task(self):
        other = get_user_model().objects.create_user("other-todo-owner", password="test")
        item = TodoItem.objects.create(
            user=other, title="Private alarm", due_at=timezone.now(),
            alarm_enabled=True,
        )
        response = self.client.post(
            reverse("todo_snooze", args=[item.pk]),
            {"minutes": "10"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 404)
        item.refresh_from_db()
        self.assertIsNone(item.snoozed_until)
