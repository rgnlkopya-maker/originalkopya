from calendar import monthrange
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db.models import Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from attendance.models import AttendanceRecord, EmployeeHRProfile
from core.models import UserProfile

User = get_user_model()


def _is_manager(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


def _service_parts(start, today):
    if not start or start > today:
        return 0, 0, 0
    years = today.year - start.year
    anniversary = date(today.year, start.month, min(start.day, monthrange(today.year, start.month)[1]))
    if anniversary > today:
        years -= 1
    anchor_year = start.year + years
    anchor = date(anchor_year, start.month, min(start.day, monthrange(anchor_year, start.month)[1]))
    months = 0
    cursor = anchor
    while True:
        month = cursor.month + 1
        year = cursor.year
        if month == 13:
            month = 1
            year += 1
        nxt = date(year, month, min(start.day, monthrange(year, month)[1]))
        if nxt > today:
            break
        months += 1
        cursor = nxt
    return years, months, (today - cursor).days


def _annual_leave_entitlement(start, as_of):
    if not start or start > as_of:
        return 0
    years, _, _ = _service_parts(start, as_of)
    return years * 14


def _selected_range(request, today, employment_start=None):
    preset = request.GET.get("preset", "this_month")
    start_raw = request.GET.get("start", "").strip()
    end_raw = request.GET.get("end", "").strip()
    if start_raw or end_raw:
        try:
            start = date.fromisoformat(start_raw) if start_raw else today
            end = date.fromisoformat(end_raw) if end_raw else today
            if start > end:
                start, end = end, start
            return start, min(end, today), "custom"
        except ValueError:
            pass
    if preset == "today": return today, today, preset
    if preset == "yesterday":
        yesterday = today - timedelta(days=1); return yesterday, yesterday, preset
    if preset == "this_week": return today - timedelta(days=today.weekday()), today, preset
    if preset == "last_month":
        first_this_month = today.replace(day=1); end = first_this_month - timedelta(days=1); return end.replace(day=1), end, preset
    if preset == "this_year": return today.replace(month=1, day=1), today, preset
    if preset == "all": return employment_start or date(2000, 1, 1), today, preset
    return today.replace(day=1), today, "this_month"


@login_required
def employee_detail(request, user_id):
    if not _is_manager(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    employee = get_object_or_404(User, pk=user_id)
    profile, _ = EmployeeHRProfile.objects.get_or_create(user=employee)
    user_profile, _ = UserProfile.objects.get_or_create(user=employee)

    if request.method == "POST":
        def parse_date(name):
            raw = request.POST.get(name, "").strip()
            return date.fromisoformat(raw) if raw else None
        try:
            username = request.POST.get("username", "").strip()
            if not username: raise ValueError("Kullanıcı adı boş olamaz.")
            if User.objects.exclude(pk=employee.pk).filter(username__iexact=username).exists():
                messages.error(request, "Bu kullanıcı adı başka bir kullanıcı tarafından kullanılıyor.")
                return redirect("employee_detail", user_id=employee.id)
            employee.username = username
            employee.first_name = request.POST.get("first_name", "").strip()
            employee.last_name = request.POST.get("last_name", "").strip()
            new_password = request.POST.get("new_password", "").strip()
            if new_password: employee.set_password(new_password)
            employee.save()
            role = request.POST.get("role", "personel")
            if role not in {"personel", "mudur", "patron"}: role = "personel"
            employee.groups.clear(); group, _ = Group.objects.get_or_create(name=role); employee.groups.add(group)
            gorev = request.POST.get("gorev", "yok")
            valid_gorevler = {value for value, _label in UserProfile.GOREV_SECENEKLERI}
            user_profile.gorev = gorev if gorev in valid_gorevler else "yok"
            user_profile.save(update_fields=["gorev"])
            profile.phone_number = request.POST.get("phone_number", "").strip()
            profile.employment_start_date = parse_date("employment_start_date")
            profile.sgk_start_date = parse_date("sgk_start_date")
            profile.birth_date = parse_date("birth_date")
            profile.annual_leave_carryover = max(0, int(request.POST.get("annual_leave_carryover") or 0))
            profile.note = request.POST.get("note", "").strip()
            profile.save()
            messages.success(request, "Personel bilgileri güncellendi.")
        except (ValueError, TypeError): messages.error(request, "Girilen bilgileri kontrol edin.")
        return redirect("employee_detail", user_id=employee.id)

    today = timezone.localdate()
    range_start, range_end, preset = _selected_range(request, today, profile.employment_start_date)
    range_records = AttendanceRecord.objects.filter(user=employee, work_date__range=(range_start, range_end))
    worked_days = range_records.filter(status="worked").count()
    leave_days = range_records.filter(status="leave").count()
    sick_days = range_records.filter(status="sick").count()
    annual_leave_period = range_records.filter(status="annual_leave").count()
    late_minutes = range_records.aggregate(v=Sum("late_minutes"))["v"] or 0
    overtime_minutes = range_records.aggregate(v=Sum("overtime_minutes"))["v"] or 0
    used_annual_leave = AttendanceRecord.objects.filter(user=employee, status="annual_leave", work_date__lte=range_end).count()
    earned_leave = _annual_leave_entitlement(profile.employment_start_date, range_end)
    total_leave = earned_leave + profile.annual_leave_carryover
    remaining_leave = max(0, total_leave - used_annual_leave)
    service_years, service_months, service_days = _service_parts(profile.employment_start_date, range_end)
    role = employee.groups.first().name if employee.groups.exists() else "personel"
    role_labels = {"personel": "Personel", "mudur": "Müdür", "patron": "Patron"}
    return render(request, "teams/employee_detail.html", {
        "employee": employee, "profile": profile, "today": today, "role": role,
        "role_label": role_labels.get(role, role.title()), "team_label": user_profile.get_gorev_display(),
        "user_profile": user_profile, "gorevler": UserProfile.GOREV_SECENEKLERI,
        "range_start": range_start, "range_end": range_end, "preset": preset,
        "service_years": service_years, "service_months": service_months, "service_days": service_days,
        "earned_leave": earned_leave, "used_annual_leave": used_annual_leave, "total_leave": total_leave,
        "remaining_leave": remaining_leave, "worked_days": worked_days, "leave_days": leave_days,
        "sick_days": sick_days, "annual_leave_period": annual_leave_period, "late_minutes": late_minutes,
        "overtime_minutes": overtime_minutes,
    })
