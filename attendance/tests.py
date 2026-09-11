from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from datetime import datetime, time

from .models import AttendanceRecord, WorkplaceSettings
from .views import _recalculate


class AttendanceDashboardRoleFilterTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        patron_group, _ = Group.objects.get_or_create(name="patron")
        manager_group, _ = Group.objects.get_or_create(name="mudur")

        self.manager = user_model.objects.create_user(
            username="takvim-yoneticisi",
            password="test",
        )
        self.manager.groups.add(manager_group)

        self.mustafa = user_model.objects.create_user(
            username="mustafa-hesabi",
            first_name="Mustafa",
            last_name="Kanyış",
            password="test",
        )
        self.mustafa.groups.add(patron_group)

        self.emine = user_model.objects.create_user(
            username="emine-hesabi",
            first_name="Emine",
            last_name="Kanyış",
            password="test",
        )
        self.emine.groups.add(patron_group)

        self.employee = user_model.objects.create_user(
            username="normal-personel",
            first_name="Normal",
            last_name="Personel",
            password="test",
        )
        self.client.force_login(self.manager)

    def test_patrons_are_not_listed_in_attendance_calendar(self):
        response = self.client.get(reverse("attendance_dashboard"))

        self.assertEqual(response.status_code, 200)
        listed_user_ids = {user.id for user in response.context["users"]}
        self.assertIn(self.employee.id, listed_user_ids)
        self.assertNotIn(self.mustafa.id, listed_user_ids)
        self.assertNotIn(self.emine.id, listed_user_ids)


class LateToleranceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="gecikme-testi")
        self.workplace = WorkplaceSettings.objects.create(pk=1, work_start=time(8, 30), work_end=time(19, 0), late_tolerance_minutes=5)

    def _record_at(self, hour, minute):
        day = timezone.localdate()
        check_in = timezone.make_aware(datetime.combine(day, time(hour, minute)), timezone.get_current_timezone())
        return AttendanceRecord(user=self.user, work_date=day, check_in=check_in)

    def test_five_minutes_late_is_within_tolerance(self):
        record = self._record_at(8, 35)
        _recalculate(record, self.workplace)
        self.assertEqual(record.late_minutes, 0)

    def test_six_minutes_late_records_full_six_minutes(self):
        record = self._record_at(8, 36)
        _recalculate(record, self.workplace)
        self.assertEqual(record.late_minutes, 6)
