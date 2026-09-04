import math
from calendar import monthrange
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import AttendanceRecord, WorkplaceSettings


def is_manager(user):
    return user.is_staff or user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


def _distance_m(lat1, lon1, lat2, lon2):
    radius = 6371000
    p1 = math.radians(float(lat1))
    p2 = math.radians(float(lat2))
    dp = math.radians(float(lat2) - float(lat1))
    dl = math.radians(float(lon2) - float(lon1))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return int(round(radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))))


def _local_dt(day, clock):
    return timezone.make_aware(datetime.combine(day, clock), timezone.get_current_timezone())


@login_required
def scan(request):
    workplace = WorkplaceSettings.get_solo()
    today = timezone.localdate()
    record = AttendanceRecord.objects.filter(user=request.user, work_date=today).first()
    return render(request, "attendance_v2/scan.html", {"workplace": workplace, "record": record})


@login_required
@require_POST
def punch(request):
    workplace = WorkplaceSettings.get_solo()
    if not workplace.location_ready:
        return JsonResponse({"ok": False, "message": "İşyeri konumu henüz yönetici tarafından tanımlanmadı."}, status=400)

    if timezone.localdate().weekday() >= 5:
        return JsonResponse({"ok": False, "message": "Cumartesi ve pazar normal çalışma günü değildir."}, status=400)

    try:
        lat = float(request.POST.get("latitude"))
        lon = float(request.POST.get("longitude"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "message": "Telefon konumu alınamadı."}, status=400)

    distance = _distance_m(lat, lon, workplace.latitude, workplace.longitude)
    now = timezone.now()
    today = timezone.localdate()
    record, _ = AttendanceRecord.objects.get_or_create(user=request.user, work_date=today)

    if not record.check_in:
        if distance > workplace.normal_radius_m:
            return JsonResponse({"ok": False, "message": f"Giriş için işyerine en fazla {workplace.normal_radius_m} metre uzakta olmalısınız. Şu an yaklaşık {distance} m."}, status=400)
        record.check_in = now
        record.check_in_latitude = lat
        record.check_in_longitude = lon
        record.check_in_distance_m = distance
        late_limit = _local_dt(today, workplace.work_start) + timedelta(minutes=workplace.late_tolerance_minutes)
        record.late_minutes = max(0, int((now - late_limit).total_seconds() // 60)) if now > late_limit else 0
        record.save()
        return JsonResponse({"ok": True, "action": "in", "message": f"Giriş kaydedildi: {timezone.localtime(now).strftime('%H:%M')}"})

    if record.check_out:
        return JsonResponse({"ok": False, "message": "Bugünkü giriş ve çıkışınız zaten tamamlandı."}, status=400)

    work_end = _local_dt(today, workplace.work_end)
    allowed_radius = workplace.overtime_radius_m if now >= work_end else workplace.normal_radius_m
    if distance > allowed_radius:
        return JsonResponse({"ok": False, "message": f"Çıkış için izin verilen alan {allowed_radius} metre. Şu an yaklaşık {distance} m."}, status=400)

    record.check_out = now
    record.check_out_latitude = lat
    record.check_out_longitude = lon
    record.check_out_distance_m = distance
    record.overtime_minutes = max(0, int((now - work_end).total_seconds() // 60)) if now > work_end else 0
    record.save()
    return JsonResponse({"ok": True, "action": "out", "message": f"Çıkış kaydedildi: {timezone.localtime(now).strftime('%H:%M')}"})


@login_required
@user_passes_test(is_manager)
def dashboard(request):
    workplace = WorkplaceSettings.get_solo()
    today = timezone.localdate()
    users = User.objects.filter(is_active=True).order_by("first_name", "username")
    records = {r.user_id: r for r in AttendanceRecord.objects.filter(work_date=today).select_related("user")}
    rows = [{"user": user, "record": records.get(user.id)} for user in users]
    return render(request, "attendance_v2/dashboard.html", {"workplace": workplace, "rows": rows, "today": today})


@login_required
@user_passes_test(is_manager)
@require_POST
def save_workplace(request):
    workplace = WorkplaceSettings.get_solo()
    try:
        workplace.latitude = float(request.POST["latitude"])
        workplace.longitude = float(request.POST["longitude"])
    except (KeyError, TypeError, ValueError):
        messages.error(request, "Geçerli bir işyeri konumu alınamadı.")
        return redirect("attendance_dashboard")
    workplace.save()
    messages.success(request, "İşyeri konumu kaydedildi.")
    return redirect("attendance_dashboard")


@login_required
@user_passes_test(is_manager)
def month_report(request, user_id, year=None, month=None):
    target_user = get_object_or_404(User, pk=user_id)
    today = timezone.localdate()
    year = year or today.year
    month = month or today.month
    last_day = monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)
    records = {r.work_date: r for r in AttendanceRecord.objects.filter(user=target_user, work_date__range=(start, end))}
    days = []
    total_late = total_overtime = absent_count = workday_count = 0
    for day_number in range(1, last_day + 1):
        d = date(year, month, day_number)
        if d.weekday() >= 5:
            continue
        workday_count += 1
        record = records.get(d)
        if not record and d <= today:
            absent_count += 1
        if record:
            total_late += record.late_minutes
            total_overtime += record.overtime_minutes
        days.append({"date": d, "record": record})
    return render(request, "attendance_v2/month_report.html", {
        "target_user": target_user, "year": year, "month": month, "days": days,
        "workday_count": workday_count, "absent_count": absent_count,
        "total_late": total_late, "total_overtime": total_overtime,
    })
