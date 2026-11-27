from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .attendance_security import AttendancePasswordGateMiddleware
from .models import AttendanceRecord


class AttendancePasswordWindowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="puantaj-admin", password="local-test-pass")
        cls.user.groups.add(Group.objects.get_or_create(name="patron")[0])

    def setUp(self):
        self.client.force_login(self.user)
        self.home = reverse("attendance_dashboard")
        self.gate = reverse("attendance_password_gate")
        self.edit = reverse("attendance_edit_record")
        clock = patch("attendance.attendance_security.time", return_value=1000)
        self.clock = clock.start()
        self.addCleanup(clock.stop)

    def unlock(self):
        return self.client.post(self.gate, {"password": "local-test-pass"})

    def test_first_open_and_direct_excel_require_password(self):
        for path in (self.home, reverse("attendance_excel")):
            self.assertRedirects(self.client.get(path), self.gate, fetch_redirect_response=False)

    def test_reload_change_month_leave_and_return_within_window(self):
        self.assertRedirects(self.unlock(), self.home, fetch_redirect_response=False)
        self.clock.return_value = 1299.999
        for path in (self.home, f"{self.home}?year=2026&month=9", f"{self.home}?view=annual"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response.headers["Cache-Control"])
        self.client.get("/", HTTP_SEC_FETCH_DEST="document")
        self.assertEqual(self.client.get(self.home).status_code, 200)
        self.assertEqual(self.client.get(reverse("attendance_excel"), {"year": 2026, "month": 9}).status_code, 200)

    def test_expiration_is_fixed_and_returns_to_same_filter(self):
        self.unlock()
        self.clock.return_value = 1299
        self.assertEqual(self.client.get(self.home).status_code, 200)
        self.clock.return_value = 1300
        destination = f"{self.home}?year=2026&month=9"
        self.assertRedirects(self.client.get(destination), self.gate, fetch_redirect_response=False)
        self.assertRedirects(self.unlock(), destination, fetch_redirect_response=False)
        self.assertEqual(self.client.get(destination).status_code, 200)

    def test_expired_ajax_returns_reauth_without_saving_or_replaying(self):
        self.unlock()
        self.clock.return_value = 1300
        data = {"user_id": self.user.pk, "work_date": "2026-11-25", "check_in": "08:30", "check_out": "19:00"}
        res = self.client.post(self.edit, data)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["reauth_url"], self.gate)
        self.assertFalse(AttendanceRecord.objects.exists())
        self.unlock()
        self.assertFalse(AttendanceRecord.objects.exists())
        self.assertTrue(self.client.post(self.edit, data).json()["ok"])
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        self.assertEqual(self.client.get(self.home).status_code, 200)

    def test_wrong_password_does_not_unlock(self):
        res = self.client.post(self.gate, {"password": "wrong"})
        self.assertContains(res, "Şifre yanlış")
        self.assertRedirects(self.client.get(self.home), self.gate, fetch_redirect_response=False)

    def test_legacy_verification_without_expiry_is_invalid(self):
        session = self.client.session
        session[AttendancePasswordGateMiddleware.VERIFIED_SESSION_KEY] = self.user.pk
        session.save()
        self.assertRedirects(self.client.get(self.home), self.gate, fetch_redirect_response=False)

    def test_unauthorized_user_cannot_unlock(self):
        employee = get_user_model().objects.create_user(username="puantaj-personel", password="local-test-pass")
        self.client.force_login(employee)
        self.assertEqual(self.unlock().status_code, 403)

    def test_verification_does_not_carry_to_different_user(self):
        self.unlock()
        other = get_user_model().objects.create_user(username="puantaj-manager", password="local-test-pass")
        other.groups.add(Group.objects.get_or_create(name="mudur")[0])
        self.client.force_login(other)
        self.assertRedirects(self.client.get(self.home), self.gate, fetch_redirect_response=False)
