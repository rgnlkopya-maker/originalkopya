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
from .push_views import send_push_to_user
from .models import PushSubscription
from .backup_center_views import manager as is_manager


EVENT_CATALOG = (
    ("Faturaya aktarılmayan yeni sevkiyat", "Fatura", "Patron ve müdür", "Uygulama içi + Push", "core.manager_notification_signals"),
    ("Fatura aktarım hatası", "Fatura", "Patron ve müdür", "Uygulama içi + Push", "core.manager_notification_signals"),
    ("Malzeme eksikliği", "Üretim", "Patron ve müdür", "Uygulama içi + Push", "core.manager_notification_signals"),
    ("Bayraklı sipariş hareketi", "Üretim", "Patron, müdür ve seçilen kişiler", "Uygulama içi + Push", "core.manager_notification_signals"),
    ("Otomatik yedekleme hatası", "Sistem", "Patron ve müdür", "Uygulama içi + Push", "core.manager_notification_signals"),
    ("Giriş güvenliği uyarısı", "Güvenlik", "Patron ve müdür", "Uygulama içi + Push", "core.manager_notification_signals"),
    ("Yeni sohbet mesajı", "Mesaj", "Sohbet üyeleri", "Mesaj ekranı + Push", "core.push_views"),
    ("Zamanlanmış hatırlatma", "Hatırlatma", "Seçili kişi, ekip veya herkes", "Hatırlatma ekranı + Push", "core.reminder_service"),
    ("Yapılacak iş alarmı", "Görev", "Görev sahibi", "Uygulama içi popup; Push için zamanlayıcı ve cihaz izni gerekir", "core.todo_service"),
    ("Yarın teslim edilecek siparişler", "Sevkiyat", "Patron ve müdür", "13.30 uygulama içi + Push", "core.todo_service"),
    ("Üretim 3 gün hareketsiz", "Üretim", "Patron ve müdür", "13.30 uygulama içi + Push", "core.todo_service"),
    ("Çek/senet vadesine 15 gün kaldı", "Finans", "Patron ve müdür", "13.30 uygulama içi + Push", "core.todo_service"),
    ("Müşteri durum değişikliği", "Müşteri", "Patron ve müdür", "09.00 sonrası uygulama içi + Push", "core.customer_monitor_service"),
    ("En kârlı müşteri liderliği değişikliği", "Müşteri", "Patron ve müdür", "20.00 uygulama içi + Push", "core.customer_monitor_service"),
    ("En fazla adet alan müşteri liderliği değişikliği", "Müşteri", "Patron ve müdür", "20.00 uygulama içi + Push", "core.customer_monitor_service"),
    ("En yüksek ciro liderliği değişikliği", "Müşteri", "Patron ve müdür", "20.00 uygulama içi + Push", "core.customer_monitor_service"),
)


@login_required
@require_http_methods(["GET", "POST"])
def notification_center(request):
    if not is_manager(request.user):
        return HttpResponseForbidden("Bildirim Merkezi yalnız patron ve müdür içindir.")

    if request.method == "POST" and request.POST.get("action") == "test_push":
        from .notification_preferences import EVENTS_BY_KEY, settings_for_user as recipient_settings_for_user
        from .manager_notification_signals import management_users

        target_id = (request.POST.get("target_user") or "").strip()
        target = get_user_model().objects.filter(pk=target_id, is_active=True).first() if target_id.isdecimal() else None
        if not target:
            messages.error(request, "Bildirim testi için geçerli bir kullanıcı seçin.")
            return redirect("notification_center")

        event_key = (request.POST.get("test_event") or "generic").strip()
        if event_key != "generic" and event_key not in EVENTS_BY_KEY:
            messages.error(request, "Geçerli bir bildirim türü seçin.")
            return redirect("notification_center")

        name = target.get_full_name() or target.username
        if event_key != "generic":
            if not management_users().filter(pk=target.pk).exists():
                messages.warning(request, f"{name}: Bu yönetim bildiriminin alıcısı değil. Test gönderilmedi.")
                return redirect("notification_center")
            _, push_on = event_delivery(recipient_settings_for_user(target), event_key)
            if not push_on:
                messages.warning(request, f"{name}: Bu bildirim türünün Push tercihi kapalı. Test gönderilmedi.")
                return redirect("notification_center")

        count = PushSubscription.objects.filter(user=target).count()
        if count == 0:
            messages.warning(request, f"{name} için kayıtlı bildirim cihazı yok. Cihazda Bildirimleri Aç seçeneğini kullanın.")
            return redirect("notification_center")

        examples = {
            "uninvoiced_shipment": ("Faturaya Aktarılmayan Yeni Sevkiyat", "Örnek sevkiyat: Fatura aktarım kontrolü bekliyor.", "/urun-kartlari/faturalar/aktarilmayan-sevkler/"),
            "invoice_failure": ("Fatura Aktarım Hatası", "Örnek fatura: Dış sistem aktarımı başarısız.", "/urun-kartlari/faturalar/"),
            "material_missing": ("Malzeme Eksikliği", "Örnek sipariş: Malzeme eksik olarak işaretlendi.", "/"),
            "flagged_stage": ("Bayraklı Siparişte Üretim Hareketi", "Örnek sipariş: Üretim aşaması güncellendi.", "/"),
            "backup_failed": ("Otomatik Yedekleme Başarısız", "Örnek yedek: Yedekleme başarısız oldu.", "/yonetim/yedekleme-merkezi/"),
            "security_lock": ("Güvenlik Uyarısı", "Örnek giriş: Güvenlik kontrolü gerekli.", "/"),
            "customer_status_changed": ("Müşteri Durumu Değişti", "Örnek: Son sevkiyat süresi nedeniyle müşteri durumu değişti.", "/reports/musteri-karsilastirma/"),
            "customer_profit_leader": ("En Kârlı Müşteri Değişti", "Örnek: Günlük lider sıralaması değişti.", "/reports/musteri-karsilastirma/"),
            "customer_quantity_leader": ("En Fazla Adet Alan Müşteri Değişti", "Örnek: Günlük adet lideri değişti.", "/reports/musteri-karsilastirma/"),
            "customer_revenue_leader": ("En Yüksek Ciroya Sahip Müşteri Değişti", "Örnek: Günlük ciro lideri değişti.", "/reports/musteri-karsilastirma/"),
            "generic": ("MoliApp Bildirim Testi", "Yönetim panelinden gönderilen deneme bildirimidir.", "/yonetim/bildirim-merkezi/"),
        }
        heading, message, destination = examples[event_key]
        accepted = send_push_to_user(
            user=target,
            title=f"[TEST] {heading}",
            body=f"Bu bir denemedir, gerçek olay oluşmadı. {message}",
            url=destination,
            tag=f"moli-notification-test-{target.pk}-{event_key}",
        )
        if accepted:
            messages.success(request, f"{name}: {heading} testi {accepted}/{count} cihazda Push servisi tarafından kabul edildi. Cihazda görünmesini kontrol edin.")
        else:
            messages.error(request, f"{name}: {heading} testi gönderilemedi. {count} kayıtlı cihaz için Push sunucusu kabul etmedi.")
        return redirect("notification_center")

    if request.method == "POST" and request.POST.get("action") == "save_preferences":
        choices = validated_choices(request.POST)
        for recipient in get_user_model().objects.filter(is_active=True).iterator():
            NotificationPreference.objects.update_or_create(
                user=recipient, defaults={"choices": choices},
            )
        messages.success(request, "Tercihler tüm aktif kullanıcılar için kaydedildi.")
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
    reminders = list(Reminder.objects.filter(is_active=True).select_related("target_user").order_by("due_at")[:3])
    return render(request, "core/notification_center.html", {
        "event_catalog": EVENT_CATALOG,
        "event_preferences": event_preferences,
        "notification_count": my_notifications.count(),
        "unread_count": my_notifications.filter(is_read=False).count(),
        "recent_notifications": my_notifications.order_by("-timestamp")[:6],
        "reminders": reminders,
        "active_reminders": Reminder.objects.filter(is_active=True).count(),
        "test_push_device_count": PushSubscription.objects.filter(user=request.user).count(),
        "test_event_choices": EVENTS,
        "push_test_users": [
            {"user": user, "device_count": count}
            for user, count in (
                (u, PushSubscription.objects.filter(user=u).count())
                for u in get_user_model().objects.filter(is_active=True).order_by("first_name", "username")
            )
        ],
        "users": get_user_model().objects.filter(is_active=True).order_by("first_name", "username"),
        "team_choices": [(key, label) for key, label in UserProfile.GOREV_SECENEKLERI if key != "yok"],
    })
