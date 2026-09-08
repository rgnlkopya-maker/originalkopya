import math
from datetime import datetime, time, timedelta

from django.db import migrations
from django.utils import timezone


def recalculate_existing(apps, schema_editor):
    AttendanceRecord = apps.get_model("attendance", "AttendanceRecord")
    WorkplaceSettings = apps.get_model("attendance", "WorkplaceSettings")
    workplace = WorkplaceSettings.objects.filter(pk=1).first()
    work_end_time = workplace.work_end if workplace and workplace.work_end else time(19, 0)
    tz = timezone.get_current_timezone()

    for record in AttendanceRecord.objects.all().iterator():
        early = 0
        overtime = record.overtime_minutes or 0

        if record.status != "worked":
            overtime = 0
        elif record.work_date.weekday() < 5 and record.check_out:
            work_end = timezone.make_aware(datetime.combine(record.work_date, work_end_time), tz)
            overtime_start = work_end + timedelta(minutes=5)
            early = max(0, math.ceil((work_end - record.check_out).total_seconds() / 60)) if record.check_out < work_end else 0
            overtime = max(0, int((record.check_out - overtime_start).total_seconds() // 60)) if record.check_out > overtime_start else 0

        record.early_leave_minutes = early
        record.overtime_minutes = overtime
        record.save(update_fields=["early_leave_minutes", "overtime_minutes"])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0011_attendancerecord_early_leave_minutes"),
    ]

    operations = [
        migrations.RunPython(recalculate_existing, reverse_noop),
    ]
