import os
from datetime import date, timedelta
from django.db import migrations


TARGET_REMAINING = {
    "selin": 11, "mert": 9, "aylin": 13, "derya": 10, "esra": 8,
    "nisa": 10, "melis": 7, "ece": 6, "burak": 12, "deniz": 11, "arda": 8,
}


def realistic_demo_leave_history(apps, schema_editor):
    if os.getenv("DEMO_MODE") != "1":
        return

    User = apps.get_model("auth", "User")
    EmployeeHRProfile = apps.get_model("attendance", "EmployeeHRProfile")
    AttendanceRecord = apps.get_model("attendance", "AttendanceRecord")

    as_of = date(2026, 10, 4)

    for username, target_remaining in TARGET_REMAINING.items():
        user = User.objects.filter(username=username).first()
        if not user:
            continue
        profile = EmployeeHRProfile.objects.filter(user=user).first()
        if not profile or not profile.employment_start_date:
            continue

        start = profile.employment_start_date
        years = as_of.year - start.year
        anniversary = start.replace(year=as_of.year)
        if anniversary > as_of:
            years -= 1
        earned = max(0, years) * 14
        total_entitlement = earned + (profile.annual_leave_carryover or 0)
        desired_used = max(0, total_entitlement - target_remaining)

        current_used = AttendanceRecord.objects.filter(
            user=user, status="annual_leave", work_date__lte=as_of
        ).count()
        needed = max(0, desired_used - current_used)
        if not needed:
            continue

        # Gecmis yillara dagit; mevcut puantaj kayitlarina dokunma.
        cursor = start + timedelta(days=365)
        added = 0
        while cursor < date(2026, 8, 1) and added < needed:
            # Sadece hafta ici; mevcut kayit varsa atla.
            if cursor.weekday() < 5 and not AttendanceRecord.objects.filter(
                user=user, work_date=cursor
            ).exists():
                AttendanceRecord.objects.create(
                    user=user,
                    work_date=cursor,
                    status="annual_leave",
                    note="Geçmiş dönem yıllık izin kaydı",
                )
                added += 1
            cursor += timedelta(days=1)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0079_enrich_eylus_demo_staff"),
        ("attendance", "0014_attendancerecord_checkout_forgotten"),
    ]

    operations = [
        migrations.RunPython(realistic_demo_leave_history, migrations.RunPython.noop),
    ]
