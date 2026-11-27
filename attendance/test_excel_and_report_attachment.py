import json
from datetime import date, datetime
from io import BytesIO
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from .absence_service import LOCAL
from .models import AttendanceRecord, EmployeeHRProfile


class AttendanceExcelAndAttachmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.admin = users.objects.create_user(username="test-patron", password="test-only-pass")
        cls.admin.groups.add(Group.objects.get_or_create(name="patron")[0])
        cls.employee = users.objects.create_user(username="test-personel")
        EmployeeHRProfile.objects.create(user=cls.employee, employment_start_date=date(2026, 10, 22),
            sgk_start_date=date(2026, 10, 20), employment_end_date=date(2026, 11, 2))
        cls.unknown = users.objects.create_user(username="test-no-date")

    def setUp(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("attendance_password_gate"), {"password": "test-only-pass"})

    def test_excel_missing_sheet_uses_earliest_start_and_shared_workdays(self):
        AttendanceRecord.objects.create(user=self.employee, work_date=date(2026, 10, 30),
            status="worked", check_in=datetime(2026, 10, 30, 8, 30, tzinfo=LOCAL))
        AttendanceRecord.objects.create(user=self.employee, work_date=date(2026, 10, 21), status="annual_leave")
        with patch("attendance.excel_views.timezone.localdate", return_value=date(2026, 11, 3)):
            response = self.client.get(reverse("attendance_excel"), {"year": 2026, "month": 10})
        self.assertEqual(response.status_code, 200)
        book = load_workbook(BytesIO(response.content))
        entries = {day.date(): (person, reason)
                   for day, person, reason, _ in list(book["Eksik Kayitlar"].values)[1:]}
        self.assertIn(date(2026, 10, 20), entries)
        self.assertNotIn(date(2026, 10, 19), entries)  # before either start
        self.assertNotIn(date(2026, 10, 21), entries)  # recorded annual leave
        self.assertNotIn(date(2026, 10, 24), entries)  # Saturday
        self.assertNotIn(date(2026, 10, 28), entries)  # half holiday
        self.assertNotIn(date(2026, 10, 29), entries)  # full holiday
        self.assertEqual(entries[date(2026, 10, 30)][1], "Cikis eksik")  # actual partial record
        self.assertIn(date(2026, 11, 2), entries)  # last eligible day
        self.assertNotIn(date(2026, 11, 3), entries)
        self.assertTrue(all(name == self.employee.username for name, _ in entries.values()))
        self.assertEqual(next(row for row in book["Donem Toplamlari"].values if row[0] == self.employee.username)[5], 1)
        self.assertTrue(any(r[4] == "Yıllık İzin" for r in list(book["Gunluk Puantaj"].values)[1:]))

    def make_report(self):
        return AttendanceRecord.objects.create(user=self.employee, work_date=date(2026, 10, 22),
            status="sick", note="Açıklama", report_image_url="https://example.invalid/report.pdf")

    def edit(self, row, **kwargs):
        return self.client.post(reverse("attendance_edit_record"), {
            "user_id": row.user_id, "work_date": row.work_date, "status": row.status, "note": row.note, **kwargs
        })

    def test_report_can_be_unlinked_without_altering_status_or_note(self):
        row = self.make_report()
        self.assertTrue(self.edit(row, remove_report_image="1").json()["ok"])
        row.refresh_from_db()
        self.assertEqual((row.report_image_url, row.status, row.note), ("", "sick", "Açıklama"))
        audit = json.loads(LogEntry.objects.latest("pk").change_message)
        self.assertTrue(audit["old"]["has_report_image"])
        self.assertFalse(audit["new"]["has_report_image"])

    def test_unchecked_preserves_the_attachment(self):
        row = self.make_report()
        self.assertTrue(self.edit(row).json()["ok"])
        row.refresh_from_db()
        self.assertEqual(row.report_image_url, "https://example.invalid/report.pdf")

    @patch("attendance.views._upload_report_image", return_value="https://example.invalid/new.pdf")
    def test_new_file_replaces_existing_even_when_remove_is_checked(self, upload):
        row = self.make_report()
        response = self.edit(row, remove_report_image="1", report_image=SimpleUploadedFile("test.pdf", b"example"))
        self.assertTrue(response.json()["ok"])
        row.refresh_from_db()
        self.assertEqual(row.report_image_url, "https://example.invalid/new.pdf")

    @patch("attendance.views._upload_report_image", side_effect=RuntimeError("synthetic failure"))
    def test_failed_replacement_leaves_previous_file_in_place(self, upload):
        row = self.make_report()
        response = self.edit(row, remove_report_image="1", report_image=SimpleUploadedFile("test.pdf", b"example"))
        self.assertEqual(response.status_code, 500)
        row.refresh_from_db()
        self.assertEqual(row.report_image_url, "https://example.invalid/report.pdf")
