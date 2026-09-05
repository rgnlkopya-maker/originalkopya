from calendar import monthrange
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from attendance.models import AttendanceRecord, EmployeeHRProfile
from core.models import OrderEvent, UserProfile
from core.services.order_status import FINANCIAL_STAGES, STATUS_LABELS

User = get_user_model()
TEAM_CHOICES = list(UserProfile.GOREV_SECENEKLERI)
if not any(value == "modelleme" for value, _label in TEAM_CHOICES):
    TEAM_CHOICES.append(("modelleme", "Modelleme"))


def _is_manager(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


def _service_parts(start, today):
    if not start or start > today: return 0, 0, 0
    years = today.year - start.year
    anniversary = date(today.year, start.month, min(start.day, monthrange(today.year, start.month)[1]))
    if anniversary > today: years -= 1
    anchor_year = start.year + years
    anchor = date(anchor_year, start.month, min(start.day, monthrange(anchor_year, start.month)[1]))
    months = 0; cursor = anchor
    while True:
        month = cursor.month + 1; year = cursor.year
        if month == 13: month = 1; year += 1
        nxt = date(year, month, min(start.day, monthrange(year, month)[1]))
        if nxt > today: break
        months += 1; cursor = nxt
    return years, months, (today - cursor).days


def _annual_leave_entitlement(start, as_of):
    if not start or start > as_of: return 0
    years, _, _ = _service_parts(start, as_of)
    return years * 14


def _selected_range(request, today, employment_start=None, employment_end=None):
    effective_today = min(today, employment_end) if employment_end else today
    preset = request.GET.get("preset", "this_month")
    start_raw = request.GET.get("start", "").strip(); end_raw = request.GET.get("end", "").strip()
    if start_raw or end_raw:
        try:
            start = date.fromisoformat(start_raw) if start_raw else effective_today
            end = date.fromisoformat(end_raw) if end_raw else effective_today
            if start > end: start, end = end, start
            return start, min(end, effective_today), "custom"
        except ValueError: pass
    if preset == "today": return effective_today, effective_today, preset
    if preset == "yesterday":
        yesterday = effective_today - timedelta(days=1); return yesterday, yesterday, preset
    if preset == "this_week": return effective_today - timedelta(days=effective_today.weekday()), effective_today, preset
    if preset == "last_month":
        first_this_month = effective_today.replace(day=1); end = first_this_month - timedelta(days=1); return end.replace(day=1), end, preset
    if preset == "this_year": return effective_today.replace(month=1, day=1), effective_today, preset
    if preset == "all": return employment_start or date(2000, 1, 1), effective_today, preset
    return effective_today.replace(day=1), effective_today, "this_month"


def _event_label(stage, value):
    return STATUS_LABELS.get(
        (stage, value),
        f"{(stage or '').replace('_durum', '').replace('_', ' ').title()} → "
        f"{(value or '').replace('_', ' ').title()}",
    )


@login_required
def user_management_view(request):
    if not _is_manager(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    all_users = User.objects.all().order_by("username")
    departed_users = all_users.filter(Q(is_active=False) | Q(hr_profile__employment_end_date__isnull=False)).distinct()
    users = all_users.exclude(pk__in=departed_users.values_list("pk", flat=True))
    profiles = {p.user_id: p for p in UserProfile.objects.filter(user__in=all_users)}
    hr_profiles = {p.user_id: p for p in EmployeeHRProfile.objects.filter(user__in=all_users)}

    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        if action == "create_user":
            username = request.POST.get("username", "").strip(); password = request.POST.get("password", "").strip()
            role = request.POST.get("role", "").strip(); gorev = request.POST.get("gorev", "yok").strip()
            first_name = request.POST.get("first_name", "").strip(); last_name = request.POST.get("last_name", "").strip()
            if not username or not password or not role:
                messages.error(request, "Kullanıcı adı, şifre ve rol zorunludur."); return redirect("user_management")
            if User.objects.filter(username=username).exists():
                messages.warning(request, f"{username} zaten mevcut ⏸️"); return redirect("user_management")
            user = User.objects.create_user(username=username, password=password, first_name=first_name, last_name=last_name)
            if role in {"personel", "mudur", "patron"}:
                group, _ = Group.objects.get_or_create(name=role); user.groups.add(group)
            valid_gorevler = {value for value, _label in TEAM_CHOICES}
            profile, _ = UserProfile.objects.get_or_create(user=user); profile.gorev = gorev if gorev in valid_gorevler else "yok"; profile.save()
            def new_date(name):
                raw = request.POST.get(name, "").strip(); return date.fromisoformat(raw) if raw else None
            hr = EmployeeHRProfile.objects.create(
                user=user,
                phone_number=request.POST.get("phone_number", "").strip(),
                national_id=request.POST.get("national_id", "").strip(),
                emergency_contact_name=request.POST.get("emergency_contact_name", "").strip(),
                emergency_contact_phone=request.POST.get("emergency_contact_phone", "").strip(),
                employment_start_date=new_date("employment_start_date"),
                employment_end_date=new_date("employment_end_date"),
                sgk_start_date=new_date("sgk_start_date"),
            )
            if hr.employment_end_date:
                user.is_active = False; user.save(update_fields=["is_active"])
            messages.success(request, f"{user.get_full_name() or username} eklendi ✅"); return redirect("user_management")
        if action == "reset_password":
            u = get_object_or_404(User, pk=request.POST.get("user_id")); new_password = request.POST.get("new_password", "").strip()
            if new_password: u.set_password(new_password); u.save(); messages.success(request, f"{u.username} için şifre güncellendi 🔐")
            else: messages.error(request, "Yeni şifre boş olamaz.")
            return redirect("user_management")
        if action == "update_gorev":
            u = get_object_or_404(User, pk=request.POST.get("user_id")); profile, _ = UserProfile.objects.get_or_create(user=u)
            gorev = request.POST.get("gorev", "yok").strip(); valid_gorevler = {value for value, _label in TEAM_CHOICES}
            profile.gorev = gorev if gorev in valid_gorevler else "yok"; profile.save(); messages.success(request, f"{u.username} görevi güncellendi 🏷️"); return redirect("user_management")
        if action == "delete_user":
            u = get_object_or_404(User, pk=request.POST.get("user_id"))
            if u == request.user: messages.warning(request, "Kendinizi silemezsiniz.")
            else: u.delete(); messages.success(request, "Kullanıcı silindi 🗑️")
            return redirect("user_management")
    return render(request, "user_management.html", {
        "users": users,
        "departed_users": departed_users,
        "profiles": profiles,
        "hr_profiles": hr_profiles,
        "GOREVLER": TEAM_CHOICES,
    })


@login_required
def employee_detail(request, user_id):
    if not _is_manager(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    employee = get_object_or_404(User, pk=user_id)
    profile, _ = EmployeeHRProfile.objects.get_or_create(user=employee)
    user_profile, _ = UserProfile.objects.get_or_create(user=employee)

    if request.method == "POST":
        action = request.POST.get("action", "edit_employee").strip()
        if action == "mark_departed":
            if employee == request.user:
                messages.error(request, "Kendi hesabınızı işten ayrılanlara taşıyamazsınız.")
                return redirect("employee_detail", user_id=employee.id)
            if not profile.employment_end_date:
                profile.employment_end_date = timezone.localdate()
                profile.save(update_fields=["employment_end_date", "updated_at"])
            employee.is_active = False
            employee.save(update_fields=["is_active"])
            messages.success(request, f"{employee.get_full_name() or employee.username} işyerinden ayrılanlar listesine taşındı.")
            return redirect("user_management")

        def parse_date(name):
            raw = request.POST.get(name, "").strip(); return date.fromisoformat(raw) if raw else None
        try:
            username = request.POST.get("username", "").strip()
            if not username: raise ValueError("Kullanıcı adı boş olamaz.")
            if User.objects.exclude(pk=employee.pk).filter(username__iexact=username).exists():
                messages.error(request, "Bu kullanıcı adı başka bir kullanıcı tarafından kullanılıyor."); return redirect("employee_detail", user_id=employee.id)
            employee.username = username; employee.first_name = request.POST.get("first_name", "").strip(); employee.last_name = request.POST.get("last_name", "").strip()
            new_password = request.POST.get("new_password", "").strip()
            if new_password: employee.set_password(new_password)
            employee.save()
            role = request.POST.get("role", "personel")
            if role not in {"personel", "mudur", "patron"}: role = "personel"
            employee.groups.clear(); group, _ = Group.objects.get_or_create(name=role); employee.groups.add(group)
            gorev = request.POST.get("gorev", "yok"); valid_gorevler = {value for value, _label in TEAM_CHOICES}
            user_profile.gorev = gorev if gorev in valid_gorevler else "yok"; user_profile.save(update_fields=["gorev"])
            profile.phone_number = request.POST.get("phone_number", "").strip()
            profile.national_id = request.POST.get("national_id", "").strip()
            profile.emergency_contact_name = request.POST.get("emergency_contact_name", "").strip()
            profile.emergency_contact_phone = request.POST.get("emergency_contact_phone", "").strip()
            profile.employment_start_date = parse_date("employment_start_date")
            profile.employment_end_date = parse_date("employment_end_date")
            profile.sgk_start_date = parse_date("sgk_start_date"); profile.birth_date = parse_date("birth_date")
            profile.annual_leave_carryover = max(0, int(request.POST.get("annual_leave_carryover") or 0)); profile.note = request.POST.get("note", "").strip(); profile.save()
            employee.is_active = not bool(profile.employment_end_date)
            employee.save(update_fields=["is_active"])
            messages.success(request, "Personel bilgileri güncellendi.")
        except (ValueError, TypeError): messages.error(request, "Girilen bilgileri kontrol edin.")
        return redirect("employee_detail", user_id=employee.id)

    today = timezone.localdate(); range_start, range_end, preset = _selected_range(request, today, profile.employment_start_date, profile.employment_end_date)
    range_records = AttendanceRecord.objects.filter(user=employee, work_date__range=(range_start, range_end))
    worked_days = range_records.filter(status="worked").count(); leave_days = range_records.filter(status="leave").count(); sick_days = range_records.filter(status="sick").count(); annual_leave_period = range_records.filter(status="annual_leave").count()
    late_minutes = range_records.aggregate(v=Sum("late_minutes"))["v"] or 0; overtime_minutes = range_records.aggregate(v=Sum("overtime_minutes"))["v"] or 0
    used_annual_leave = AttendanceRecord.objects.filter(user=employee, status="annual_leave", work_date__lte=range_end).count(); earned_leave = _annual_leave_entitlement(profile.employment_start_date, range_end)
    total_leave = earned_leave + profile.annual_leave_carryover; remaining_leave = max(0, total_leave - used_annual_leave); service_years, service_months, service_days = _service_parts(profile.employment_start_date, range_end)

    work_events_qs = (
        OrderEvent.objects
        .select_related("order", "order__musteri")
        .filter(
            user=employee.username,
            event_type="stage",
            timestamp__date__range=(range_start, range_end),
        )
        .exclude(stage__in=FINANCIAL_STAGES)
        .order_by("-timestamp", "-id")
    )
    raw_counts = (
        work_events_qs.values("stage", "value")
        .annotate(count=Count("id"))
        .order_by("stage", "value")
    )
    operation_counts = [
        {"stage": row["stage"], "value": row["value"], "label": _event_label(row["stage"], row["value"]), "count": row["count"]}
        for row in raw_counts
    ]
    work_events_total = work_events_qs.count()
    work_events_page = Paginator(work_events_qs, 100).get_page(request.GET.get("work_page"))
    for event in work_events_page:
        event.operation_label = _event_label(event.stage, event.value)

    role = employee.groups.first().name if employee.groups.exists() else "personel"; role_labels = {"personel": "Personel", "mudur": "Müdür", "patron": "Patron"}
    team_label = dict(TEAM_CHOICES).get(user_profile.gorev, user_profile.gorev.title())
    return render(request, "teams/employee_detail.html", {
        "employee": employee, "profile": profile, "today": today, "role": role, "role_label": role_labels.get(role, role.title()), "team_label": team_label, "user_profile": user_profile, "gorevler": TEAM_CHOICES,
        "range_start": range_start, "range_end": range_end, "preset": preset, "service_years": service_years, "service_months": service_months, "service_days": service_days,
        "earned_leave": earned_leave, "used_annual_leave": used_annual_leave, "total_leave": total_leave, "remaining_leave": remaining_leave,
        "worked_days": worked_days, "leave_days": leave_days, "sick_days": sick_days, "annual_leave_period": annual_leave_period, "late_minutes": late_minutes, "overtime_minutes": overtime_minutes,
        "operation_counts": operation_counts, "work_events_total": work_events_total, "work_events_page": work_events_page,
    })
