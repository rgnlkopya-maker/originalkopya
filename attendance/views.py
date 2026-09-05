import io
import math
import os
import uuid
from calendar import monthrange
from datetime import date, datetime

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from supabase import create_client

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


def _nearest_workplace(workplace, lat, lon):
    locations = workplace.active_locations()
    if not locations:
        return None, None
    distances = [(name, _distance_m(lat, lon, wlat, wlon)) for name, wlat, wlon in locations]
    return min(distances, key=lambda item: item[1])


def _local_dt(day, clock):
    return timezone.make_aware(datetime.combine(day, clock), timezone.get_current_timezone())


def _recalculate(record, workplace):
    record.late_minutes = 0
    record.overtime_minutes = 0
    if record.status != "worked":
        return
    if record.work_date.weekday() >= 5:
        if record.check_in and record.check_out and record.check_out >= record.check_in:
            record.overtime_minutes = max(0, int((record.check_out - record.check_in).total_seconds() // 60))
        return
    work_start = _local_dt(record.work_date, workplace.work_start)
    work_end = _local_dt(record.work_date, workplace.work_end)
    if record.check_in and record.check_in > work_start:
        record.late_minutes = max(0, int((record.check_in - work_start).total_seconds() // 60))
    if record.check_out and record.check_out > work_end:
        record.overtime_minutes = max(0, int((record.check_out - work_end).total_seconds() // 60))


def _upload_report_image(uploaded_file, user_id, work_date):
    if not uploaded_file:
        return ""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Supabase ayarları eksik.")
    ext = os.path.splitext(uploaded_file.name)[1].lower() or ".jpg"
    path = f"attendance/reports/{user_id}/{work_date.isoformat()}_{uuid.uuid4().hex}{ext}"
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    bucket = client.storage.from_(settings.SUPABASE_BUCKET_NAME)
    bucket.upload(path, uploaded_file.read(), file_options={"content-type": uploaded_file.content_type or "application/octet-stream", "upsert": "false"})
    return bucket.get_public_url(path)


@login_required
def scan(request):
    workplace = WorkplaceSettings.get_solo()
    today = timezone.localdate()
    record = AttendanceRecord.objects.filter(user=request.user, work_date=today).first()
    return render(request, "attendance_v2/scan.html", {"workplace": workplace, "record": record})


@login_required
@user_passes_test(is_patron)
def attendance_qr_image(request):
    target_url = request.build_absolute_uri(reverse("attendance_scan"))
    qr = qrcode.QRCode(version=None, box_size=12, border=4)
    qr.add_data(target_url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


@login_required
@user_passes_test(is_patron)
def attendance_qr_print(request):
    target_url = request.build_absolute_uri(reverse("attendance_scan"))
    return render(request, "attendance_v2/qr_print.html", {"target_url": target_url})


@login_required
@require_POST
def punch(request):
    workplace = WorkplaceSettings.get_solo()
    if not workplace.active_locations():
        return JsonResponse({"ok": False, "message": "İşyeri konumu henüz yönetici tarafından tanımlanmadı."}, status=400)
    try:
        lat = float(request.POST.get("latitude")); lon = float(request.POST.get("longitude"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "message": "Telefon konumu alınamadı."}, status=400)
    location_name, distance = _nearest_workplace(workplace, lat, lon)
    now = timezone.now(); today = timezone.localdate(); is_weekend = today.weekday() >= 5
    record, _ = AttendanceRecord.objects.get_or_create(user=request.user, work_date=today)
    if record.status in {"leave", "annual_leave", "sick"}:
        return JsonResponse({"ok": False, "message": "Bugün için izin/rapor kaydı var. Patron kullanıcı değiştirebilir."}, status=400)
    record.status = "worked"
    if not record.check_in:
        allowed_radius = workplace.overtime_radius_m if is_weekend else workplace.normal_radius_m
        if distance > allowed_radius:
            return JsonResponse({"ok": False, "message": f"Giriş için izin verilen alan {allowed_radius} metre. En yakın işyerine yaklaşık {distance} m."}, status=400)
        record.check_in = now; record.check_in_latitude = lat; record.check_in_longitude = lon; record.check_in_distance_m = distance
        _recalculate(record, workplace); record.save()
        return JsonResponse({"ok": True, "action": "in", "message": f"Giriş kaydedildi: {timezone.localtime(now).strftime('%H:%M')} · {location_name}"})
    if record.check_out:
        return JsonResponse({"ok": False, "message": "Bugünkü giriş ve çıkışınız zaten tamamlandı."}, status=400)
    work_end = _local_dt(today, workplace.work_end)
    allowed_radius = workplace.overtime_radius_m if is_weekend or now >= work_end else workplace.normal_radius_m
    if distance > allowed_radius:
        return JsonResponse({"ok": False, "message": f"Çıkış için izin verilen alan {allowed_radius} metre. En yakın işyerine yaklaşık {distance} m."}, status=400)
    record.check_out = now; record.check_out_latitude = lat; record.check_out_longitude = lon; record.check_out_distance_m = distance
    _recalculate(record, workplace); record.save()
    return JsonResponse({"ok": True, "action": "out", "message": f"Çıkış kaydedildi: {timezone.localtime(now).strftime('%H:%M')} · {location_name}"})


@login_required
@user_passes_test(is_manager)
def dashboard(request):
    workplace = WorkplaceSettings.get_solo(); today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year)); month = int(request.GET.get("month", today.month))
        if month < 1 or month > 12: raise ValueError
    except (TypeError, ValueError):
        year, month = today.year, today.month

    hidden_attendance_names = {
        "emine kanyış", "oğuzhan kanyış", "mustafa kanyış", "osman kanyış",
        "mehmet şener", "mehmet", "mihriban", "patron",
    }
    active_users = User.objects.filter(is_active=True).order_by("first_name", "username")
    users = []
    for user in active_users:
        full_name = user.get_full_name().strip().casefold(); username = user.username.strip().casefold()
        if full_name in hidden_attendance_names or username in hidden_attendance_names: continue
        if "mihriban" in hidden_attendance_names and (full_name == "mihriban" or full_name.startswith("mihriban ")): continue
        users.append(user)

    last_day = monthrange(year, month)[1]; start = date(year, month, 1); end = date(year, month, last_day)
    records_qs = list(AttendanceRecord.objects.filter(work_date__range=(start, end)).select_related("user"))
    records = {(r.user_id, r.work_date): r for r in records_qs}; matrix_rows = []
    for day_number in range(1, last_day + 1):
        d = date(year, month, day_number)
        matrix_rows.append({"date": d, "is_weekend": d.weekday() >= 5, "cells": [{"user": user, "record": records.get((user.id, d))} for user in users]})
    monthly_totals = []
    for user in users:
        user_records = [r for r in records_qs if r.user_id == user.id]
        monthly_totals.append({"user": user, "total_late": sum(r.late_minutes or 0 for r in user_records), "total_overtime": sum(r.overtime_minutes or 0 for r in user_records), "leave_days": sum(1 for r in user_records if r.status == "leave"), "annual_leave_days": sum(1 for r in user_records if r.status == "annual_leave"), "sick_days": sum(1 for r in user_records if r.status == "sick")})
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1); next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    return render(request, "attendance_v2/dashboard.html", {"workplace": workplace, "users": users, "matrix_rows": matrix_rows, "monthly_totals": monthly_totals, "today": today, "year": year, "month": month, "prev_year": prev_year, "prev_month": prev_month, "next_year": next_year, "next_month": next_month, "can_edit": is_patron(request.user)})


@login_required
@user_passes_test(is_patron)
@require_POST
def edit_record(request):
    workplace = WorkplaceSettings.get_solo(); target_user = get_object_or_404(User, pk=request.POST.get("user_id"))
    try: work_date = date.fromisoformat(request.POST.get("work_date", ""))
    except ValueError: return JsonResponse({"ok": False, "message": "Geçersiz tarih."}, status=400)
    status = (request.POST.get("status") or "worked").strip(); valid_statuses = {choice[0] for choice in AttendanceRecord.STATUS_CHOICES}
    if status not in valid_statuses: return JsonResponse({"ok": False, "message": "Geçersiz durum."}, status=400)
    check_in_text = (request.POST.get("check_in") or "").strip(); check_out_text = (request.POST.get("check_out") or "").strip(); note = (request.POST.get("note") or "").strip(); uploaded_report = request.FILES.get("report_image")
    record = AttendanceRecord.objects.filter(user=target_user, work_date=work_date).first()
    if not check_in_text and not check_out_text and status == "worked" and not note and not uploaded_report and not record: return JsonResponse({"ok": True, "message": "Değişiklik yok."})
    record, _ = AttendanceRecord.objects.get_or_create(user=target_user, work_date=work_date); record.status = status; record.note = note
    if status in {"worked", "leave"}:
        try:
            record.check_in = _local_dt(work_date, datetime.strptime(check_in_text, "%H:%M").time()) if check_in_text else None
            record.check_out = _local_dt(work_date, datetime.strptime(check_out_text, "%H:%M").time()) if check_out_text else None
        except ValueError: return JsonResponse({"ok": False, "message": "Saat formatı geçersiz."}, status=400)
        if record.check_in and record.check_out and record.check_out < record.check_in: return JsonResponse({"ok": False, "message": "İzin/çıkış saati giriş saatinden önce olamaz."}, status=400)
    else: record.check_in = None; record.check_out = None
    if uploaded_report:
        try: record.report_image_url = _upload_report_image(uploaded_report, target_user.id, work_date)
        except Exception as exc: return JsonResponse({"ok": False, "message": f"Rapor görseli yüklenemedi: {exc}"}, status=400)
    if request.POST.get("remove_report_image") == "1": record.report_image_url = ""
    _recalculate(record, workplace); record.save(); return JsonResponse({"ok": True, "message": "Puantaj kaydı güncellendi."})


@login_required
@user_passes_test(is_manager)
@require_POST
def save_workplace(request):
    workplace = WorkplaceSettings.get_solo(); slot = (request.POST.get("location_slot") or "primary").strip()
    try:
        latitude = float(request.POST["latitude"]); longitude = float(request.POST["longitude"])
    except (KeyError, TypeError, ValueError):
        messages.error(request, "Geçerli bir işyeri konumu alınamadı."); return redirect("attendance_dashboard")
    if slot == "second":
        workplace.second_location_name = "Gaziemir"; workplace.second_latitude = latitude; workplace.second_longitude = longitude
        message = "Gaziemir konumu kaydedildi."
    else:
        workplace.latitude = latitude; workplace.longitude = longitude; message = "Çankaya konumu kaydedildi."
    workplace.save(); messages.success(request, message); return redirect("attendance_dashboard")


@login_required
@user_passes_test(is_manager)
def month_report(request, user_id, year=None, month=None):
    target_user = get_object_or_404(User, pk=user_id); today = timezone.localdate(); year = year or today.year; month = month or today.month
    last_day = monthrange(year, month)[1]; start = date(year, month, 1); end = date(year, month, last_day)
    records = {r.work_date: r for r in AttendanceRecord.objects.filter(user=target_user, work_date__range=(start, end))}
    days = []; total_late = total_overtime = absent_count = workday_count = 0
    for day_number in range(1, last_day + 1):
        d = date(year, month, day_number); record = records.get(d)
        if d.weekday() < 5:
            workday_count += 1
            if not record and d <= today: absent_count += 1
        if record: total_late += record.late_minutes; total_overtime += record.overtime_minutes
        days.append({"date": d, "record": record, "is_weekend": d.weekday() >= 5})
    return render(request, "attendance_v2/month_report.html", {"target_user": target_user, "year": year, "month": month, "days": days, "workday_count": workday_count, "absent_count": absent_count, "total_late": total_late, "total_overtime": total_overtime})
