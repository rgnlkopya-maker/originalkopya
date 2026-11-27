"""Read-only attendance Excel export for the selected 6th-to-5th payroll periods."""
from calendar import month_name
from datetime import date, timedelta
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from .absence_service import is_employed_on, is_ordinary_workday
from .models import AttendanceRecord, EmployeeHRProfile
from .views import attendance_calendar_users, is_manager


def _period(year, month):
    start = date(year, month, 6)
    end = date(year + (month == 12), 1 if month == 12 else month + 1, 5)
    return start, end


def _minutes(n):
    return f"{n // 60} sa {n % 60:02d} dk"


def _style_sheet(ws, widths):
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions
    for idx, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="253B68")
        cell.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 25


@login_required
def attendance_excel(request):
    if not is_manager(request.user):
        return HttpResponseForbidden("Puantaj raporu indirme yetkiniz bulunmuyor.")
    try:
        year = int(request.GET.get("year", ""))
        month = int(request.GET.get("month", "1"))
        if not (2000 <= year <= 2100 and 1 <= month <= 12):
            raise ValueError
    except (ValueError, TypeError):
        return HttpResponseBadRequest("Geçersiz dönem.")
    mode = request.GET.get("view", "monthly")
    if mode not in {"monthly", "annual"}:
        return HttpResponseBadRequest("Geçersiz görünüm.")
    start, end = (_period(year, month) if mode == "monthly" else (date(year, 1, 6), date(year + 1, 1, 5)))
    users = list(attendance_calendar_users())
    today = timezone.localdate()
    employment_dates = {
        uid: (hire, sgk, ended)
        for uid, hire, sgk, ended in EmployeeHRProfile.objects.filter(user__in=users).values_list(
            "user_id", "employment_start_date", "sgk_start_date", "employment_end_date"
        )
    }
    records = list(AttendanceRecord.objects.filter(work_date__range=(start, end), user__in=users).select_related("user"))
    by_key = {(r.user_id, r.work_date): r for r in records}
    book = Workbook()
    daily = book.active
    daily.title = "Gunluk Puantaj"
    daily.append(["Tarih", "Personel", "Giris", "Cikis", "Durum", "Gec (dk)", "Erken (dk)", "Fazla mesai (dk)", "Aciklama"])
    status_names = dict(AttendanceRecord.STATUS_CHOICES)
    missing = book.create_sheet("Eksik Kayitlar")
    missing.append(["Tarih", "Personel", "Sorun", "Aciklama"])
    for day_offset in range((end - start).days + 1):
        day = start + timedelta(days=day_offset)
        check_blank = day < today and is_ordinary_workday(day)
        for user in users:
            record = by_key.get((user.pk, day))
            name = user.get_full_name() or user.username
            if record:
                local_in = record.check_in.astimezone().strftime("%H:%M") if record.check_in else ""
                local_out = record.check_out.astimezone().strftime("%H:%M") if record.check_out else ""
                daily.append([day, name, local_in, local_out, status_names.get(record.status, record.status), record.late_minutes, record.early_leave_minutes, record.overtime_minutes, record.note])
                if record.status == "worked" and record.check_in and not record.check_out and day < today:
                    missing.append([day, name, "Cikis eksik", record.note])
                elif record.status == "worked" and record.check_out and not record.check_in:
                    missing.append([day, name, "Giris eksik", record.note])
            elif check_blank and is_employed_on(day, *employment_dates.get(user.pk, (None, None, None))):
                # Missing record does not automatically mean absence; show for review only.
                missing.append([day, name, "Kayit yok - kontrol gerekli", ""])
    summary = book.create_sheet("Donem Toplamlari", 1)
    summary.append(["Personel", "Gec (dk)", "Erken (dk)", "Fazla mesai (dk)", "Izin (gun)", "Yillik izin (gun)", "Rapor (gun)", "Gelmedi (gun)"])
    for user in users:
        group = [r for r in records if r.user_id == user.pk]
        summary.append([user.get_full_name() or user.username,
                        sum(r.late_minutes or 0 for r in group),
                        sum(r.early_leave_minutes or 0 for r in group),
                        sum(r.overtime_minutes or 0 for r in group),
                        sum(r.status == "leave" for r in group),
                        sum(r.status == "annual_leave" for r in group),
                        sum(r.status == "sick" for r in group),
                        sum(r.status == "absent" for r in group)])
    summary.append(["GENEL TOPLAM"] + [sum(summary.cell(row=i, column=j).value or 0 for i in range(2, summary.max_row + 1)) for j in range(2, 9)])
    for ws, widths in ((daily, [15, 28, 12, 12, 18, 14, 14, 21, 48]), (summary, [28, 14, 14, 21, 15, 20, 16, 16]), (missing, [15, 28, 28, 45])):
        _style_sheet(ws, widths)
        for row in ws.iter_rows(min_row=2):
            if isinstance(row[0].value, date):
                row[0].number_format = "DD.MM.YYYY"
    buffer = BytesIO()
    book.save(buffer)
    period_label = f"{year}" if mode == "annual" else f"{year}-{month:02d}"
    response = HttpResponse(buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="Moli_Puantaj_{period_label}.xlsx"'
    response["Cache-Control"] = "private, no-store"
    return response
