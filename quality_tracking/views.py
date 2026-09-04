from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from attendance.models import AttendanceRecord
from core.models import Order, OrderEvent
from .models import QualityIssue

User = get_user_model()


def is_manager(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


def _date_range(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    start_raw = (request.GET.get("start_date") or "").strip()
    end_raw = (request.GET.get("end_date") or "").strip()
    try:
        start_date = datetime.strptime(start_raw, "%Y-%m-%d").date() if start_raw else month_start
    except ValueError:
        start_date = month_start
    try:
        end_date = datetime.strptime(end_raw, "%Y-%m-%d").date() if end_raw else today
    except ValueError:
        end_date = today
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min), tz)
    return start_date, end_date, start_dt, end_dt


@login_required
@user_passes_test(is_manager)
def order_quality_issues(request, order_id):
    order = get_object_or_404(Order.objects.select_related("musteri"), pk=order_id)
    issues = order.quality_issues.prefetch_related("sorumlu_personeller").all()
    users = User.objects.filter(is_active=True).exclude(username__in=["patron"]).order_by("username")
    if request.method == "POST":
        konu = (request.POST.get("konu") or "").strip()
        aciklama = (request.POST.get("aciklama") or "").strip()
        asama = (request.POST.get("asama") or "GENEL").strip()
        personel_ids = request.POST.getlist("personeller")
        valid_stages = {value for value, _ in QualityIssue.STAGE_CHOICES}
        if not konu or not aciklama:
            messages.error(request, "Hata konusu ve açıklama zorunludur.")
        elif asama not in valid_stages:
            messages.error(request, "Geçersiz üretim aşaması.")
        else:
            issue = QualityIssue.objects.create(order=order, konu=konu, aciklama=aciklama, asama=asama, kaydeden=request.user)
            if personel_ids:
                issue.sorumlu_personeller.set(User.objects.filter(id__in=personel_ids, is_active=True))
            messages.success(request, "Hata / müşteri şikayeti kaydedildi. Siparişin son durumu değiştirilmedi.")
            return redirect("quality_tracking:order_issues", order_id=order.id)
    return render(request, "quality_tracking/order_issues.html", {"order": order, "issues": issues, "users": users, "stage_choices": QualityIssue.STAGE_CHOICES})


@login_required
@user_passes_test(is_manager)
def resolve_issue(request, issue_id):
    issue = get_object_or_404(QualityIssue, pk=issue_id)
    if request.method == "POST":
        issue.durum = "COZULDU"
        issue.cozum_notu = (request.POST.get("cozum_notu") or "").strip()
        issue.resolved_at = timezone.now()
        issue.save(update_fields=["durum", "cozum_notu", "resolved_at"])
        messages.success(request, "Hata kaydı çözüldü olarak işaretlendi.")
    return redirect("quality_tracking:order_issues", order_id=issue.order_id)


@login_required
@user_passes_test(is_manager)
def reopen_issue(request, issue_id):
    issue = get_object_or_404(QualityIssue, pk=issue_id)
    if request.method == "POST":
        issue.durum = "ACIK"
        issue.resolved_at = None
        issue.save(update_fields=["durum", "resolved_at"])
        messages.success(request, "Hata kaydı tekrar açıldı.")
    return redirect("quality_tracking:order_issues", order_id=issue.order_id)


@login_required
@user_passes_test(is_manager)
def issue_report(request):
    qs = QualityIssue.objects.select_related("order", "order__musteri", "kaydeden").prefetch_related("sorumlu_personeller")
    durum = (request.GET.get("durum") or "").strip()
    personel = (request.GET.get("personel") or "").strip()
    q = (request.GET.get("q") or "").strip()
    if durum in {"ACIK", "COZULDU"}:
        qs = qs.filter(durum=durum)
    if personel:
        qs = qs.filter(sorumlu_personeller__username=personel)
    if q:
        qs = qs.filter(Q(konu__icontains=q) | Q(aciklama__icontains=q) | Q(order__siparis_numarasi__icontains=q) | Q(order__urun_kodu__icontains=q) | Q(order__musteri__ad__icontains=q))
    qs = qs.distinct()
    users = User.objects.filter(is_active=True).exclude(username="patron").order_by("username")
    return render(request, "quality_tracking/issue_report.html", {"issues": qs, "users": users, "selected_durum": durum, "selected_personel": personel, "q": q})


def _personnel_detail_context(request, target_user):
    start_date, end_date, start_dt, end_dt = _date_range(request)
    production_events = (OrderEvent.objects.filter(Q(user=target_user.username) | Q(ortak_calisanlar__icontains=target_user.username), timestamp__gte=start_dt, timestamp__lt=end_dt, event_type="stage").select_related("order", "order__musteri").order_by("-timestamp"))
    issues = (QualityIssue.objects.filter(sorumlu_personeller=target_user, created_at__gte=start_dt, created_at__lt=end_dt).select_related("order", "order__musteri", "kaydeden").prefetch_related("sorumlu_personeller").distinct().order_by("-created_at"))
    attendance = AttendanceRecord.objects.filter(user=target_user, work_date__range=(start_date, end_date)).order_by("-work_date")

    timeline = []
    for record in attendance:
        if record.check_in:
            timeline.append({"timestamp": record.check_in, "kind": "attendance_in", "title": "İşe giriş", "detail": record.get_status_display(), "attendance": record})
        if record.check_out:
            detail = f"Fazla mesai: {record.overtime_minutes} dk" if record.overtime_minutes else "Çıkış kaydı"
            timeline.append({"timestamp": record.check_out, "kind": "attendance_out", "title": "İşten çıkış", "detail": detail, "attendance": record})
    for event in production_events:
        shared = bool(event.user != target_user.username and target_user.username.lower() in (event.ortak_calisanlar or "").lower())
        timeline.append({"timestamp": event.timestamp, "kind": "production", "title": f"{event.stage} → {event.value}", "detail": event.aciklama or ("Ortak çalışan olarak kayıtlı" if shared else ""), "event": event, "order": event.order, "shared": shared})
    for issue in issues:
        timeline.append({"timestamp": issue.created_at, "kind": "issue", "title": f"Hata / Şikayet: {issue.konu}", "detail": issue.aciklama, "issue": issue, "order": issue.order})
    timeline.sort(key=lambda item: item["timestamp"], reverse=True)

    unique_order_ids = {event.order_id for event in production_events}
    total_overtime = sum(r.overtime_minutes or 0 for r in attendance)
    total_late = sum(r.late_minutes or 0 for r in attendance)
    open_issue_count = sum(1 for issue in issues if issue.durum == "ACIK")
    return {
        "target_user": target_user,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "timeline": timeline,
        "production_count": production_events.count(),
        "order_count": len(unique_order_ids),
        "attendance_count": attendance.count(),
        "overtime_minutes": total_overtime,
        "late_minutes": total_late,
        "issue_count": issues.count(),
        "open_issue_count": open_issue_count,
        "issues": issues,
    }


@login_required
@user_passes_test(is_manager)
def personnel_detail(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)
    return render(request, "quality_tracking/personnel_detail.html", _personnel_detail_context(request, target_user))


@login_required
@user_passes_test(is_manager)
def personnel_detail_username(request, username):
    target_user = get_object_or_404(User, username=username)
    return render(request, "quality_tracking/personnel_detail.html", _personnel_detail_context(request, target_user))
