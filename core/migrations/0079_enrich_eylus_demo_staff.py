import os
from datetime import date, timedelta
from django.db import migrations
from django.db.models import Min


STAFF = {
    "selin": {"full": "Selin Aras", "birth": date(1993, 5, 14), "tenure_years": 7, "carry": 5},
    "mert": {"full": "Mert Akin", "birth": date(1997, 9, 22), "tenure_years": 5, "carry": 3},
    "aylin": {"full": "Aylin Kara", "birth": date(1989, 2, 8), "tenure_years": 8, "carry": 7},
    "derya": {"full": "Derya Sen", "birth": date(1992, 11, 3), "tenure_years": 6, "carry": 4},
    "esra": {"full": "Esra Yildiz", "birth": date(1998, 7, 19), "tenure_years": 4, "carry": 2},
    "nisa": {"full": "Nisa Eren", "birth": date(1995, 1, 27), "tenure_years": 5, "carry": 4},
    "melis": {"full": "Melis Kaya", "birth": date(1999, 4, 11), "tenure_years": 3, "carry": 2},
    "ece": {"full": "Ece Demir", "birth": date(2001, 8, 30), "tenure_years": 2, "carry": 1},
    "burak": {"full": "Burak Tas", "birth": date(1991, 6, 17), "tenure_years": 6, "carry": 5},
    "deniz": {"full": "Deniz Acar", "birth": date(1988, 12, 5), "tenure_years": 7, "carry": 6},
    "arda": {"full": "Arda Gunes", "birth": date(1996, 3, 25), "tenure_years": 4, "carry": 3},
}


def enrich_demo_staff(apps, schema_editor):
    if os.getenv("DEMO_MODE") != "1":
        return

    User = apps.get_model("auth", "User")
    Group = apps.get_model("auth", "Group")
    EmployeeHRProfile = apps.get_model("attendance", "EmployeeHRProfile")
    AttendanceRecord = apps.get_model("attendance", "AttendanceRecord")
    OrderEvent = apps.get_model("core", "OrderEvent")

    personel_group, _ = Group.objects.get_or_create(name="personel")

    # Seed hareketleri tam adla yazmisti. Personel detay/raporlar username ile
    # filtreledigi icin EYLUS demo hareketlerini gercek kullaniciya bagla.
    for username, cfg in STAFF.items():
        OrderEvent.objects.filter(user=cfg["full"]).update(user=username)

    for idx, (username, cfg) in enumerate(STAFF.items(), start=1):
        user = User.objects.filter(username=username).first()
        if not user:
            continue

        user.groups.add(personel_group)

        first_attendance = (
            AttendanceRecord.objects.filter(user=user)
            .aggregate(v=Min("work_date"))["v"]
        )
        first_event_dt = (
            OrderEvent.objects.filter(user=username)
            .aggregate(v=Min("timestamp"))["v"]
        )
        first_event = first_event_dt.date() if first_event_dt else None
        evidence_dates = [d for d in (first_attendance, first_event) if d]
        first_evidence = min(evidence_dates) if evidence_dates else date(2026, 8, 1)

        # Ise baslama daima sistemdeki ilk faaliyetten once olsun.
        start = first_evidence - timedelta(days=(365 * cfg["tenure_years"] + idx * 11))
        sgk_start = start

        profile, _ = EmployeeHRProfile.objects.get_or_create(user=user)
        profile.phone_number = f"0500 000 00 {idx:02d}"
        profile.national_id = ""
        profile.emergency_contact_name = f"Demo Yakini {idx}"
        profile.emergency_contact_phone = f"0500 100 00 {idx:02d}"
        profile.employment_start_date = start
        profile.employment_end_date = None
        profile.sgk_start_date = sgk_start
        profile.birth_date = cfg["birth"]
        profile.annual_leave_carryover = cfg["carry"]
        profile.chronic_conditions = "Yok"
        profile.medications = "Yok"
        profile.note = "EYLUS demo personel profili"
        profile.save()

        # Var olan puantaji bozmak yerine, secili gunleri izin/rapor olarak
        # isaretle. Boylece personel karti ve puantaj raporlari ayni veriyi okur.
        records = list(
            AttendanceRecord.objects.filter(user=user)
            .order_by("work_date", "id")
        )
        if len(records) >= 12:
            annual = records[(idx * 3) % len(records)]
            annual.status = "annual_leave"
            annual.note = "Planli yillik izin"
            annual.check_in = None
            annual.check_out = None
            annual.late_minutes = 0
            annual.early_leave_minutes = 0
            annual.overtime_minutes = 0
            annual.checkout_forgotten = False
            annual.save()

        if len(records) >= 20 and idx % 2 == 0:
            leave = records[(idx * 5 + 7) % len(records)]
            if leave.pk != annual.pk:
                leave.status = "leave"
                leave.note = "Mazeret izni"
                leave.check_in = None
                leave.check_out = None
                leave.late_minutes = 0
                leave.early_leave_minutes = 0
                leave.overtime_minutes = 0
                leave.checkout_forgotten = False
                leave.save()

        if len(records) >= 28 and idx in {1, 4, 7, 10}:
            sick = records[(idx * 7 + 9) % len(records)]
            if sick.status == "worked":
                sick.status = "sick"
                sick.note = "1 gunluk rapor"
                sick.check_in = None
                sick.check_out = None
                sick.late_minutes = 0
                sick.early_leave_minutes = 0
                sick.overtime_minutes = 0
                sick.checkout_forgotten = False
                sick.save()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0078_seed_demo_data"),
        ("attendance", "0014_attendancerecord_checkout_forgotten"),
    ]

    operations = [
        migrations.RunPython(enrich_demo_staff, migrations.RunPython.noop),
    ]
