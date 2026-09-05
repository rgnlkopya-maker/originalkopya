from calendar import monthrange
from datetime import date

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


def _annual_leave_entitlement(start, today):
    if not start or start > today:
        return 0
    years, _, _ = _service_parts(start, today)
    return years * 14


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
            if not username:
                raise ValueError("Kullanıcı adı boş olamaz.")
            if User.objects.exclude(pk=employee.pk).filter(username__iexact=username).exists():
                messages.error(request, "Bu kullanıcı adı başka bir kullanıcı tarafından kullanılıyor.")
                return redirect("employee_detail", user_id=employee.id)

            employee.username = username
            employee.first_name = request.POST.get("first_name", "").strip()
            employee.last_name = request.POST.get("last_name", "").strip()

            new_password = request.POST.get("new_password", "").strip()
            if new_password:
                employee.set_password(new_password)
            employee.save()

            role = request.POST.get("role", "personel")
            if role not in {"personel", "mudur", "patron"}:
                role = "personel"
            employee.groups.clear()
            group, _ = Group.objects.get_or_create(name=role)
            employee.groups.add(group)

            gorev = request.POST.get("gorev", "yok")
            valid_gorevler = {value for value, _label in UserProfile.GOREV_SECENEKLERI}
            user_profile.gorev = gorev if gorev in valid_gorevler else "yok"
            user_profile.save(update_fields=["gorev"])

            profile.employment_start_date = parse_date("employment_start_date")
            profile.sgk_start_date = parse_date("sgk_start_date")
            profile.birth_date = parse_date("birth_date")
            profile.annual_leave_carryover = max(0, int(request.POST.get("annual_leave_carryover") or 0))
            profile.note = request.POST.get("note", "").strip()
            profile.save()
            messages.success(request, "Personel bilgileri güncellendi.")
        except (ValueError, TypeError):
            messages.error(request, "Girilen bilgileri kontrol edin.")
        return redirect("employee_detail", user_id=employee.id)

    today = timezone.localdate()
    month_records = AttendanceRecord.objects.filter(
        user=employee, work_date__year=today.year, work_date__month=today.month
    )
    all_records = AttendanceRecord.objects.filter(user=employee)

    worked_days = month_records.filter(status="worked").count()
    leave_days = month_records.filter(status="leave").count()
    sick_days = month_records.filter(status="sick").count()
    annual_leave_month = month_records.filter(status="annual_leave").count()
    late_minutes = month_records.aggregate(v=Sum("late_minutes"))["v"] or 0
    overtime_minutes = month_records.aggregate(v=Sum("overtime_minutes"))["v"] or 0

    used_annual_leave = all_records.filter(status="annual_leave").count()
    earned_leave = _annual_leave_entitlement(profile.employment_start_date, today)
    total_leave = earned_leave + profile.annual_leave_carryover
    remaining_leave = max(0, total_leave - used_annual_leave)
    service_years, service_months, service_days = _service_parts(profile.employment_start_date, today)

    role = employee.groups.first().name if employee.groups.exists() else "personel"
    role_labels = {"personel": "Personel", "mudur": "Müdür", "patron": "Patron"}
    team = user_profile.get_gorev_display()

    return render(request, "teams/employee_detail.html", {
        "employee": employee,
        "profile": profile,
        "today": today,
        "role": role,
        "role_label": role_labels.get(role, role.title()),
        "team_label": team,
        "user_profile": user_profile,
        "gorevler": UserProfile.GOREV_SECENEKLERI,
        "service_years": service_years,
        "service_months": service_months,
        "service_days": service_days,
        "earned_leave": earned_leave,
        "used_annual_leave": used_annual_leave,
        "total_leave": total_leave,
        "remaining_leave": remaining_leave,
        "worked_days": worked_days,
        "leave_days": leave_days,
        "sick_days": sick_days,
        "annual_leave_month": annual_leave_month,
        "late_minutes": late_minutes,
        "overtime_minutes": overtime_minutes,
    })
