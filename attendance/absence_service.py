"""Record attendance gaps on completed working days, using the existing scheduler."""
from datetime import date, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from .models import AttendanceAbsenceRun, AttendanceRecord, EmployeeHRProfile

LOCAL = ZoneInfo("Europe/Istanbul")
FIRST_DAY = date(2026, 11, 27)
RUN_AT = time(20, 0)
AUTO_ABSENCE_NOTE = "Otomatik: 20.00 kontrolünde giriş veya çıkış kaydı bulunamadı. Gerekirse durumu düzenleyin."

# 2429 sayılı Kanun; dini tarihler Diyanet (2026) ve DHMİ (2027).
# https://vakithesaplama.diyanet.gov.tr/2429_kanun.php
# https://vakithesaplama.diyanet.gov.tr/dinigunler.php?yil=2026
# https://dhmi.gov.tr/AIPDocuments/LT_GEN_2_1_en.pdf
# Arefelerde ve 28 Ekim'de otomatik tam gün devamsızlık yazılmaz.
FIXED_HOLIDAYS = {(1, 1), (4, 23), (5, 1), (5, 19), (7, 15), (8, 30), (10, 28), (10, 29)}
RELIGIOUS_HOLIDAYS_START = {2026: ((3, 20), (5, 27)), 2027: ((3, 9), (5, 16))}


def is_ordinary_workday(day):
    if day.weekday() >= 5 or (day.month, day.day) in FIXED_HOLIDAYS:
        return False
    first_days = RELIGIOUS_HOLIDAYS_START.get(day.year)
    if not first_days:
        return False  # Do not mark absences until a year's holiday calendar is verified.
    for month_day, length in zip(first_days, (3, 4)):
        first = date(day.year, *month_day)
        if first - timedelta(days=1) <= day < first + timedelta(days=length):
            return False
    return True


def is_employed_on(day, hire, sgk, ended):
    """Use the earlier recorded start date; never infer an unknown start."""
    starts = [start for start in (hire, sgk) if start]
    return bool(starts and min(starts) <= day and (ended is None or day <= ended))


def process_daily_absences(now=None):
    """Process today once. No presence is inferred and no older day is filled."""
    local = (now or timezone.now()).astimezone(LOCAL)
    day = local.date()
    if day < FIRST_DAY or local.time() < RUN_AT:
        return {"status": "not_due"}
    if day.year not in RELIGIOUS_HOLIDAYS_START:
        return {"status": "unverified_holiday_calendar"}
    if not is_ordinary_workday(day):
        return {"status": "non_workday"}
    if AttendanceAbsenceRun.objects.filter(work_date=day).exists():
        return {"status": "already_processed"}

    from .views import attendance_calendar_users

    with transaction.atomic():
        # Unique daily claim; failures roll back both the claim and the entries.
        _, claimed = AttendanceAbsenceRun.objects.get_or_create(work_date=day)
        if not claimed:
            return {"status": "already_processed"}
        roster = [user.pk for user in attendance_calendar_users()]
        eligible = []
        for user_id, hire, sgk, ended in EmployeeHRProfile.objects.filter(
            user_id__in=roster,
        ).values_list("user_id", "employment_start_date", "sgk_start_date", "employment_end_date"):
            if is_employed_on(day, hire, sgk, ended):
                eligible.append(user_id)
        records = AttendanceRecord.objects.filter(user_id__in=eligible, work_date=day)
        existing = set(records.values_list("user_id", flat=True))
        AttendanceRecord.objects.bulk_create([
            AttendanceRecord(user_id=uid, work_date=day, status="absent", note=AUTO_ABSENCE_NOTE)
            for uid in eligible if uid not in existing
        ], ignore_conflicts=True)
        return {"status": "completed", "marked": records.filter(status="absent", note=AUTO_ABSENCE_NOTE).count()}
