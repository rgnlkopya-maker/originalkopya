from datetime import date, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from .absence_service import AUTO_ABSENCE_NOTE, FIRST_DAY, LOCAL, is_ordinary_workday, process_daily_absences
from .models import AttendanceAbsenceRun, AttendanceRecord, EmployeeHRProfile, WorkplaceSettings


def at(day=FIRST_DAY, hour=20, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=LOCAL)


class DailyAbsenceTests(TestCase):
    def employee(self, name, hire=None, sgk=None, ended=None, active=True, patron=False):
        user = get_user_model().objects.create_user(username=name, password="local-pass", is_active=active)
        if patron:
            user.groups.add(Group.objects.get_or_create(name="patron")[0])
        EmployeeHRProfile.objects.create(user=user, employment_start_date=hire, sgk_start_date=sgk,
                                         employment_end_date=ended)
        return user

    def test_picks_earlier_date_and_respects_roster_and_end(self):
        later = FIRST_DAY + timedelta(days=4)
        earlier = FIRST_DAY - timedelta(days=4)
        first = self.employee("hire-earlier", hire=earlier, sgk=later)
        second = self.employee("sgk-earlier", hire=later, sgk=earlier)
        third = self.employee("sgk-only", sgk=FIRST_DAY)
        fourth = self.employee("hire-only", hire=FIRST_DAY)
        self.employee("both-future", hire=later, sgk=later)
        self.employee("no-dates")
        self.employee("ended", hire=earlier, ended=earlier)
        self.employee("inactive", hire=earlier, active=False)
        self.employee("owner", hire=earlier, patron=True)
        self.assertEqual(process_daily_absences(at()), {"status": "completed", "marked": 4})
        self.assertSetEqual(set(AttendanceRecord.objects.values_list("user_id", flat=True)),
                            {first.id, second.id, third.id, fourth.id})
        self.assertTrue(all(r.status == "absent" and not r.check_in and not r.check_out
                            for r in AttendanceRecord.objects.all()))

    def test_no_history_no_early_run_and_weekends_and_holidays(self):
        self.employee("employee", hire=FIRST_DAY - timedelta(days=10))
        self.assertEqual(process_daily_absences(at(FIRST_DAY - timedelta(days=1)))["status"], "not_due")
        self.assertEqual(process_daily_absences(at(hour=19, minute=59))["status"], "not_due")
        self.assertEqual(process_daily_absences(at(date(2026, 11, 28)))["status"], "non_workday")
        self.assertEqual(process_daily_absences(at(date(2027, 3, 9)))["status"], "non_workday")
        self.assertEqual(process_daily_absences(at(date(2028, 2, 2)))["status"], "unverified_holiday_calendar")
        self.assertFalse(is_ordinary_workday(date(2027, 3, 8)))
        self.assertFalse(is_ordinary_workday(date(2027, 10, 28)))
        self.assertFalse(AttendanceRecord.objects.exists())
        self.assertFalse(AttendanceAbsenceRun.objects.exists())

    def test_preserves_any_record_and_does_not_rerun(self):
        for status in ("leave", "annual_leave", "sick", "other", "worked"):
            user = self.employee(status, hire=FIRST_DAY)
            AttendanceRecord.objects.create(user=user, work_date=FIRST_DAY, status=status,
                                            check_in=at(hour=8) if status == "worked" else None)
        missing = self.employee("missing", hire=FIRST_DAY)
        self.assertEqual(process_daily_absences(at())["marked"], 1)
        self.assertEqual(AttendanceRecord.objects.filter(status="absent").get().user, missing)
        self.assertEqual(process_daily_absences(at(minute=30))["status"], "already_processed")
        self.assertEqual(AttendanceAbsenceRun.objects.count(), 1)

    def test_failed_run_can_retry_without_half_written_state(self):
        self.employee("missing", hire=FIRST_DAY)
        with patch.object(AttendanceRecord.objects, "bulk_create", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                process_daily_absences(at())
        self.assertFalse(AttendanceAbsenceRun.objects.exists())
        self.assertEqual(process_daily_absences(at(minute=1))["marked"], 1)

    def test_report_and_excel_show_absence_then_manual_annual_leave(self):
        owner = self.employee("owner", patron=True)
        employee = self.employee("staff", sgk=FIRST_DAY)
        process_daily_absences(at())
        self.client.force_login(owner)
        self.client.post(reverse("attendance_password_gate"), {"password":"local-pass"})
        home = reverse("attendance_dashboard")
        res = self.client.get(home, {"year":2026, "month":11})
        self.assertEqual(res.context["grand_totals"]["absent_days"], 1)
        self.assertContains(res, "Gelmedi")
        report = self.client.get(reverse("attendance_month_report", args=[employee.pk, 2026, 11]))
        self.assertEqual(report.context["totals"]["absent"], 1)
        expo = self.client.get(reverse("attendance_excel"), {"year":2026, "month":11})
        book = load_workbook(BytesIO(expo.content))
        self.assertEqual(book["Donem Toplamlari"]["H3"].value, 1)
        edit = self.client.post(reverse("attendance_edit_record"), {"user_id":employee.pk, "work_date":FIRST_DAY,
                                "status":"annual_leave", "note":AUTO_ABSENCE_NOTE})
        self.assertTrue(edit.json()["ok"])
        row = AttendanceRecord.objects.get(user=employee)
        self.assertEqual((row.status, row.note), ("annual_leave", ""))
        self.assertEqual(process_daily_absences(at(minute=1))["status"], "already_processed")
        new = self.client.get(home, {"year":2026, "month":11})
        self.assertEqual(new.context["grand_totals"]["absent_days"], 0)
        self.assertEqual(new.context["grand_totals"]["annual_leave_days"], 1)

    @patch("attendance.views._device_for_request")
    @patch("attendance.views._nearest_workplace", return_value=("İş yeri", 0))
    @patch("attendance.views.qr_entry_permit_valid")
    def test_qr_does_not_leave_empty_row_on_failure_and_clears_auto_absence(self, permit, place, device):
        user = self.employee("staff", sgk=FIRST_DAY)
        device.return_value = (SimpleNamespace(save=lambda **kwargs: None), "approved")
        WorkplaceSettings.objects.filter(pk=1).update(latitude=38, longitude=27)
        self.client.force_login(user)
        with patch("attendance.views.timezone.localdate", return_value=FIRST_DAY):
            with patch("attendance.views.timezone.now", return_value=at(minute=1)):
                url = reverse("attendance_punch")
                permit.return_value = False
                self.assertEqual(self.client.post(url, {"latitude":38,"longitude":27}).status_code, 403)
                self.assertFalse(AttendanceRecord.objects.exists())
                process_daily_absences(at())
                permit.return_value = True
                self.assertEqual(self.client.post(url, {"latitude":38,"longitude":27}).json()["action"], "in")
        row = AttendanceRecord.objects.get(user=user)
        self.assertEqual((row.status, row.note), ("worked", ""))
        self.assertIsNotNone(row.check_in)
