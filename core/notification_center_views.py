"""Manager-facing notification control center.

This dashboard reports the actual notification routes and manages existing
Reminder records. It intentionally does not claim configurable event toggles.
"""
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Notification, UserProfile, NotificationPreference
from .notification_preferences import EVENTS, event_delivery, settings_for_user, validated_choices
from .reminder_models import Reminder
from .backup_center_views import manager as is_manager


EVENT_CATALOG = (
    ("Sipariş bilgisi güncellendi", "Sipariş", "Patron ve müdür", "Uygulama içi", "core.notification_service"),
    ("Faturaya aktarılmayan yeni sevkiyat", "Fatura", "Patron ve müdür", "Uygulama içi + Push", "core.manager_notification_signals"),
    ("Fatura aktarım hatası", "Fatura", "Patron ve müdür", "Uygulama içi + Push", "core.manager_notification_signals"),
    ("Malzeme eksikliği", "Üretim", "Patron ve müdür", "Uygulama içi + Push", "core.manager_notification_signals"),
    ("Bayraklı sipariş hareketi", "Üretim", "Patron, müdür ve seçilen kişiler", "Uygulama içi + Push", "core.manager_notification_signals"),
    ("Otomatik yedekleme hatası", "Sistem", "Patron ve müdür", "Uygulama içi + Push", "core.manager_notification_signals"),
    ("Giriş güvenliği uyarısı", "Güvenlik", "Patron ve müdür", "Uygulama içi + Push", "core.manager_notification_signals"),
    ("Yeni sohbet mesajı", "Mesaj", "Sohbet üyeleri", "Mesaj ekranı + Push", "core.push_views"),
    ("Zamanlanmış hatırlatma", "Hatırlatma", "Seçili kişi, ekip veya herkes", "Hatırlatma ekranı + Push", "core.reminder_service"),
    ("Yapılacak iş alarmı", "Görev", "Görev sahibi", "Görev ekranı; Push işleyicisi mevcut, zamanlayıcısı doğrulanmadı", "core.todo_service"),
)


@login_required
@require_http_methods(["GET", "POST"])
def notification_center(request):
    if not is_manager(request.user):
        return HttpResponseForbidden("Bildirim Merkezi yalnız patron ve müdür içindir.")

    if request.method == "POST" and request.POST.get("action") == "save_preferences":
        choices = validated_choices(request.POST)
        NotificationPreference.objects.update_or_create(
            user=request.user, defaults={"choices": choices},
        )
        messages.success(request, "Bildirim tercihleriniz kaydedildi.")
        return redirect("notification_center")

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()[:160]
        note = (request.POST.get("message") or "").strip()
        due_text = (request.POST.get("due_at") or "").strip()
        target_type = (request.POST.get("target_type") or "user").strip()
        repeat = (request.POST.get("repeat") or "none").strip()
        target_gorev = (request.POST.get("target_gorev") or "").strip()
        try:
            naive = datetime.strptime(due_text, "%Y-%m-%dT%H:%M")
            due_at = timezone.make_aware(naive, timezone.get_current_timezone())
            interval = int(request.POST.get("notify_interval_minutes") or "15")
            if interval not in {5, 10, 15, 30, 60, 120}:
                raise ValueError("invalid interval")
        except (TypeError, ValueError):
            messages.error(request, "Hatırlatma tarihi, saati veya tekrar aralığı geçersiz.")
            return redirect("notification_center")

        if not title:
            messages.error(request, "Hatırlatma başlığı boş olamaz.")
            return redirect("notification_center")
        if due_at <= timezone.now():
            messages.error(request, "Hatırlatma zamanı gelecekte olmalıdır.")
            return redirect("notification_center")

        target_user = None
        if target_type == "user":
            raw_id = request.POST.get("target_user") or str(request.user.pk)
            target_user = get_user_model().objects.filter(pk=raw_id, is_active=True).first()
            if not target_user:
                messages.error(request, "Geçerli bir kullanıcı seçin.")
                return redirect("notification_center")
            target_gorev = ""
        elif target_type == "team":
            valid_roles = {key for key, _ in UserProfile.GOREV_SECENEKLERI if key != "yok"}
            if target_gorev not in valid_roles:
                messages.error(request, "Geçerli bir ekip seçin.")
                return redirect("notification_center")
        elif target_type == "all":
            target_gorev = ""
        else:
            messages.error(request, "Bildirim hedefi geçersiz.")
            return redirect("notification_center")

        Reminder.objects.create(
            title=title, message=note, due_at=due_at,
            target_type=target_type, target_user=target_user, target_gorev=target_gorev,
            repeat=repeat if repeat in {"none", "daily", "weekly", "monthly"} else "none",
            notify_interval_minutes=interval, created_by=request.user,
        )
        messages.success(request, "Hatırlatma oluşturuldu.")
        return redirect("notification_center")

    current_choices = settings_for_user(request.user)
    event_preferences = []
    for key, name, critical, _ in EVENTS:
        in_app, push = event_delivery(current_choices, key)
        event_preferences.append({
            "key": key, "name": name, "critical": critical,
            "in_app": in_app, "push": push,
        })

    my_notifications = Notification.objects.filter(user=request.user)
    reminders = list(Reminder.objects.select_related("target_user").order_by("-is_active", "due_at")[:8])
    return render(request, "core/notification_center.html", {
        "event_catalog": EVENT_CATALOG,
        "event_preferences": event_preferences,
        "notification_count": my_notifications.count(),
        "unread_count": my_notifications.filter(is_read=False).count(),
        "recent_notifications": my_notifications.order_by("-timestamp")[:6],
        "reminders": reminders,
        "active_reminders": Reminder.objects.filter(is_active=True).count(),
        "users": get_user_model().objects.filter(is_active=True).order_by("first_name", "username"),
        "team_choices": [(key, label) for key, label in UserProfile.GOREV_SECENEKLERI if key != "yok"],
    })
