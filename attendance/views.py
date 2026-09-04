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


def is_patron(user):
    return user.is_superuser or user.username.lower() == "patron" or user.groups.filter(name="patron").exists()


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


def _recalculate(record, workplace):
    work_start = _local_dt(record.work_date, workplace.work_start)
    work_end = _local_dt(record.work_date, workplace.work_end)
    record.late_minutes = 0
    record.overtime_minutes = 0

    if record.work_date.weekday() >= 5:
        if record.check_in and record.check_out and record.check_out >= record.check_in:
            record.overtime_minutes = max(0, int((record.check_out - record.check_in).total_seconds() // 60))
        return

    if record.check_in and record.check_in > work_start:
        record.late_minutes = max(0, int((record.check_in - work_start).total_seconds() // 60))
    if record.check_out and record.check_out > work_end:
        record.overtime_minutes = max(0, int((record.check_out - work_end).total_seconds() // 60))


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

    try:
        lat = float(request.POST.get("latitude"))
        lon = float(request.POST.get("longitude"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "message": "Telefon konumu alınamadı."}, status=400)

    distance = _distance_m(lat, lon, workplace.latitude, workplace.longitude)
    now = timezone.now()
    today = timezone.localdate()
    is_weekend = today.weekday() >= 5
    record, _ = AttendanceRecord.objects.get_or_create(user=request.user, work_date=today)

    if not record.check_in:
        allowed_radius = workplace.overtime_radius_m if is_weekend else workplace.normal_radius_m
        if distance > allowed_radius:
            return JsonResponse({"ok": False, "message": f"Giriş için izin verilen alan {allowed_radius} metre. Şu an yaklaşık {distance} m."}, status=400)
        record.check_in = now
        record.check_in_latitude = lat
        record.check_in_longitude = lon
        record.check_in_distance_m = distance
        _recalculate(record, workplace)
        record.save()
        return JsonResponse({"ok": True, "action": "in", "message": f"Giriş kaydedildi: {timezone.localtime(now).strftime('%H:%M')}"})

    if record.check_out:
        return JsonResponse({"ok": False, "message": "Bugünkü giriş ve çıkışınız zaten tamamlandı."}, status=400)

    work_end = _local_dt(today, workplace.work_end)
    allowed_radius = workplace.overtime_radius_m if is_weekend or now >= work_end else workplace.normal_radius_m
    if distance > allowed_radius:
        return JsonResponse({"ok": False, "message": f"Çıkış için izin verilen alan {allowed_radius} metre. Şu an yaklaşık {distance} m."}, status=400)

    record.check_out = now
    record.check_out_latitude = lat
    record.check_out_longitude = lon
    record.check_out_distance_m = distance
    _recalculate(record, workplace)
    record.save()
    return JsonResponse({"ok": True, "action": "out", "message": f"Çıkış kaydedildi: {timezone.localtime(now).strftime('%H:%M')}"})


@login_required
@user_passes_test(is_manager)
def dashboard(request):
    workplace = WorkplaceSettings.get_solo()
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        if month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError):
        year, month = today.year, today.month

    users = list(User.objects.filter(is_active=True).order_by("first_name", "username"))
    last_day = monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)
    records = {
        (r.user_id, r.work_date): r
        for r in AttendanceRecord.objects.filter(work_date__range=(start, end)).select_related("user")
    }

    matrix_rows = []
    for day_number in range(1, last_day + 1):
        d = date(year, month, day_number)
        cells = [{"user": user, "record": records.get((user.id, d))} for user in users]
        matrix_rows.append({"date": d, "is_weekend": d.weekday() >= 5, "cells": cells})

    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    return render(request, "attendance_v2/dashboard.html", {
        "workplace": workplace,
        "users": users,
        "matrix_rows": matrix_rows,
        "today": today,
        "year": year,
        "month": month,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "can_edit": is_patron(request.user),
    })


@login_required
@user_passes_test(is_patron)
@require_POST
def edit_record(request):
    workplace = WorkplaceSettings.get_solo()
    target_user = get_object_or_404(User, pk=request.POST.get("user_id"))
    try:
        work_date = date.fromisoformat(request.POST.get("work_date", ""))
    except ValueError:
        return JsonResponse({"ok": False, "message": "Geçersiz tarih."}, status=400)

    check_in_text = (request.POST.get("check_in") or "").strip()
    check_out_text = (request.POST.get("check_out") or "").strip()
    record = AttendanceRecord.objects.filter(user=target_user, work_date=work_date).first()

    if not check_in_text and not check_out_text:
        if record:
            record.delete()
        return JsonResponse({"ok": True, "message": "Puantaj kaydı kaldırıldı."})

    record, _ = AttendanceRecord.objects.get_or_create(user=target_user, work_date=work_date)

    try:
        if check_in_text:
            check_in_clock = datetime.strptime(check_in_text, "%H:%M").time()
            record.check_in = _local_dt(work_date, check_in_clock)
        else:
            record.check_in = None

        if check_out_text:
            check_out_clock = datetime.strptime(check_out_text, "%H:%M").time()
            record.check_out = _local_dt(work_date, check_out_clock)
        else:
            record.check_out = None
    except ValueError:
        return JsonResponse({"ok": False, "message": "Saat formatı geçersiz."}, status=400)

    if record.check_in and record.check_out and record.check_out < record.check_in:
        return JsonResponse({"ok": False, "message": "Çıkış saati giriş saatinden önce olamaz."}, status=400)

    _recalculate(record, workplace)
    record.save()
    return JsonResponse({
        "ok": True,
        "message": "Puantaj kaydı güncellendi.",
        "check_in": timezone.localtime(record.check_in).strftime("%H:%M") if record.check_in else "",
        "check_out": timezone.localtime(record.check_out).strftime("%H:%M") if record.check_out else "",
        "late_minutes": record.late_minutes,
        "overtime_minutes": record.overtime_minutes,
    })


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
        record = records.get(d)
        if d.weekday() < 5:
            workday_count += 1
            if not record and d <= today:
                absent_count += 1
        if record:
            total_late += record.late_minutes
            total_overtime += record.overtime_minutes
        days.append({"date": d, "record": record, "is_weekend": d.weekday() >= 5})
    return render(request, "attendance_v2/month_report.html", {
        "target_user": target_user, "year": year, "month": month, "days": days,
        "workday_count": workday_count, "absent_count": absent_count,
        "total_late": total_late, "total_overtime": total_overtime,
    })
