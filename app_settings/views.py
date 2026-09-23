from datetime import time

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import redirect, render

from attendance.models import AttendanceRecord, WorkplaceSettings
from .access import has_access, has_full_access
from .models import SystemSettings, UserAccess, UserFavorite

User = get_user_model()

PERMISSION_FIELDS = [
    ('can_view_orders', 'Siparişleri Gör'),
    ('can_create_orders', 'Sipariş Oluştur'),
    ('can_edit_orders', 'Siparişi Düzenle'),
    ('can_update_production', 'Üretim Panelini Kullan'),
    ('can_delete_orders', 'Sipariş Sil'),
    ('can_view_folio_link', 'Siparişte Föy Bağlantısını Gör'),
    ('can_view_depots', 'Depoları Gör'),
    ('can_view_reports', 'Raporları Gör'),
    ('can_view_costs', 'Maliyetleri Gör'),
    ('can_view_personnel', 'Personel Raporlarını Gör'),
    ('can_view_attendance', 'Puantaj & Mesaiyi Gör'),
    ('can_view_assistant', 'Asistanı Gör'),
    ('can_manage_quality', 'Hata / Şikayet İşlemleri'),
    ('can_view_shipping_finance', 'Sevkiyat Finansını Gör'),
    ('can_manage_users', 'Kullanıcı Yönetimi'),
    ('can_view_settings', 'Ayarları Gör / Değiştir'),
]


def _time_value(value, fallback):
    try:
        h, m = (value or '').split(':')[:2]
        return time(int(h), int(m))
    except Exception:
        return fallback


@login_required
def settings_home(request):
    if not has_access(request.user, 'can_view_settings'):
        return render(request, 'app_settings/forbidden.html', status=403)

    system = SystemSettings.get_solo()
    workplace = WorkplaceSettings.get_solo()
    users = User.objects.filter(is_active=True).order_by('username')
    for user in users:
        UserAccess.objects.get_or_create(user=user)

    if request.method == 'POST':
        section = request.POST.get('section')

        if section == 'general':
            system.company_name = request.POST.get('company_name', '').strip() or 'Moli Tekstil'
            system.company_phone = request.POST.get('company_phone', '').strip()
            system.company_email = request.POST.get('company_email', '').strip()
            system.company_address = request.POST.get('company_address', '').strip()
            system.default_order_type = request.POST.get('default_order_type', 'SERI')
            try:
                system.default_delivery_days = max(0, int(request.POST.get('default_delivery_days', 30)))
            except ValueError:
                pass
            system.save()
            messages.success(request, 'Firma ve sipariş ayarları kaydedildi.')

        elif section == 'attendance':
            workplace.name = request.POST.get('workplace_name', '').strip() or 'Moli Tekstil'
            workplace.work_start = _time_value(request.POST.get('work_start'), workplace.work_start)
            workplace.work_end = _time_value(request.POST.get('work_end'), workplace.work_end)
            try:
                workplace.late_tolerance_minutes = max(0, int(request.POST.get('late_tolerance_minutes', 0)))
                workplace.normal_radius_m = max(1, int(request.POST.get('normal_radius_m', 50)))
                workplace.overtime_radius_m = max(1, int(request.POST.get('overtime_radius_m', 100)))
            except ValueError:
                pass
            workplace.save()
            from attendance.views import _recalculate
            for record in AttendanceRecord.objects.all().iterator():
                _recalculate(record, workplace)
                record.save(update_fields=["late_minutes", "early_leave_minutes", "overtime_minutes"])
            messages.success(request, 'Puantaj ve mesai ayarları kaydedildi.')

        elif section == 'finance':
            system.default_currency = request.POST.get('default_currency', 'TRY')
            try:
                system.tcmb_update_hour = min(23, max(0, int(request.POST.get('tcmb_update_hour', 9))))
            except ValueError:
                pass
            system.finance_enabled = request.POST.get('finance_enabled') == 'on'
            system.save()
            messages.success(request, 'Finans ayarları kaydedildi.')

        elif section == 'quality':
            system.quality_categories = request.POST.get('quality_categories', '').strip()
            system.notify_late_orders = request.POST.get('notify_late_orders') == 'on'
            system.notify_upcoming_delivery = request.POST.get('notify_upcoming_delivery') == 'on'
            system.notify_open_quality_issue = request.POST.get('notify_open_quality_issue') == 'on'
            system.save()
            messages.success(request, 'Kalite ve bildirim ayarları kaydedildi.')

        elif section == 'permissions':
            target = User.objects.filter(pk=request.POST.get('user_id')).first()
            if target:
                access, _ = UserAccess.objects.get_or_create(user=target)
                for field, _label in PERMISSION_FIELDS:
                    setattr(access, field, request.POST.get(field) == 'on')
                access.save()
                messages.success(request, f'{target.username} kullanıcısının yetkileri güncellendi.')

        return redirect('settings_home')

    return render(request, 'app_settings/settings.html', {
        'system': system,
        'workplace': workplace,
        'users': users,
        'permission_fields': PERMISSION_FIELDS,
    })


@login_required
@require_POST
def toggle_staff_access(request):
    if not has_full_access(request.user):
        return JsonResponse({"ok": False, "message": "Bu işlem için yetkiniz yok."}, status=403)

    system = SystemSettings.get_solo()
    system.staff_access_enabled = not system.staff_access_enabled
    system.save(update_fields=["staff_access_enabled", "updated_at"])
    return JsonResponse({
        "ok": True,
        "enabled": system.staff_access_enabled,
        "message": "Personel erişimi açıldı." if system.staff_access_enabled else "Personel erişimi kapatıldı.",
    })


@login_required
def favorites_list(request):
    rows = list(
        UserFavorite.objects.filter(user=request.user)
        .values("id", "title", "path")
    )
    return JsonResponse({"ok": True, "favorites": rows})


@login_required
@require_POST
def favorite_toggle(request):
    title = (request.POST.get("title") or "").strip()[:180]
    path = (request.POST.get("path") or "").strip()[:500]

    if not path.startswith("/") or path.startswith("//"):
        return JsonResponse({"ok": False, "message": "Geçersiz sayfa yolu."}, status=400)
    if path.startswith("/logout") or path.startswith("/admin"):
        return JsonResponse({"ok": False, "message": "Bu sayfa favorilere eklenemez."}, status=400)

    existing = UserFavorite.objects.filter(user=request.user, path=path).first()
    if existing:
        existing.delete()
        return JsonResponse({"ok": True, "favorited": False})

    if not title:
        title = "Favori Sayfa"
    favorite = UserFavorite.objects.create(user=request.user, title=title, path=path)
    return JsonResponse({
        "ok": True,
        "favorited": True,
        "favorite": {"id": favorite.id, "title": favorite.title, "path": favorite.path},
    })
