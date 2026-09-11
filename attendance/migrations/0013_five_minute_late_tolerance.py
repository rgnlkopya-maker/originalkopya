from datetime import datetime, time

from django.db import migrations, models
from django.utils import timezone


def set_tolerance_and_recalculate(apps, schema_editor):
    AttendanceRecord = apps.get_model("attendance", "AttendanceRecord")
    WorkplaceSettings = apps.get_model("attendance", "WorkplaceSettings")
    workplace, _ = WorkplaceSettings.objects.get_or_create(pk=1)
    workplace.late_tolerance_minutes = 5
    workplace.save(update_fields=["late_tolerance_minutes"])
    work_start_time = workplace.work_start or time(8, 30)
    tz = timezone.get_current_timezone()
    for record in AttendanceRecord.objects.all().iterator():
        late = 0
        if record.status == "worked" and record.work_date.weekday() < 5 and record.check_in:
            work_start = timezone.make_aware(datetime.combine(record.work_date, work_start_time), tz)
            actual_late = max(0, int((record.check_in - work_start).total_seconds() // 60))
            if actual_late > 5:
                late = actual_late
        record.late_minutes = late
        record.save(update_fields=["late_minutes"])


class Migration(migrations.Migration):
    dependencies = [("attendance", "0012_recalculate_early_leave_and_overtime")]
    operations = [
        migrations.AlterField(model_name="workplacesettings", name="late_tolerance_minutes", field=models.PositiveIntegerField(default=5)),
        migrations.RunPython(set_tolerance_and_recalculate, migrations.RunPython.noop),
    ]
