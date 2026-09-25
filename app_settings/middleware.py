from django.shortcuts import redirect
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import time

from .access import has_feature_access, has_full_access
from .permission_registry import feature_for_path


BREAK_WINDOWS = (
    (time(10, 0), time(10, 15)),
    (time(13, 0), time(14, 0)),
    (time(16, 0), time(16, 15)),
)


def staff_break_active(now=None):
    current = (now or timezone.localtime()).time().replace(tzinfo=None)
    return any(start <= current < end for start, end in BREAK_WINDOWS)


class MoliAccessMiddleware:
    """
    Mevcut rol/yetki sistemini değiştirmez.
    Personel için yalnızca aktif mesaiyi uygulamaya giriş kapısı olarak kullanır.
    Mesai başlamadan önce sadece puantaj giriş/çıkış akışı kullanılabilir.
    """

    STAFF_PRE_ATTENDANCE_PATHS = {
        "/attendance/",
        "/attendance/punch/",
        "/attendance/qr-giris/",
        "/attendance/qr-giris/dogrula/",
        "/mesai-sonrasi-konum/",
        "/mesai-sonrasi-konum/dogrula/",
        "/logout/",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(request.user, "is_authenticated", False):
            return self.get_response(request)

        real_user = request.user
        request.real_user = real_user
        request.is_user_preview = False

        preview_user_id = request.session.get("moli_preview_user_id")
        preview_exit_path = reverse("preview_user_exit")
        if preview_user_id and has_full_access(real_user) and request.path != preview_exit_path:
            User = get_user_model()
            preview_user = User.objects.filter(pk=preview_user_id, is_active=True).first()
            if preview_user and not has_full_access(preview_user):
                request.preview_user = preview_user
                request.user = preview_user
                request.is_user_preview = True
            else:
                request.session.pop("moli_preview_user_id", None)

        # Normal personelde mesai kapısı uygulanır; Patron/Müdür önizleme modunda bu kapı atlanır.
        if not request.is_user_preview and not has_full_access(request.user):
            from attendance.models import AttendanceRecord
            from .models import SystemSettings

            system = SystemSettings.get_solo()

            # Önceki günlerden çözülmemiş "çıkış unutuldu" kaydı varsa personel
            # MoliApp'e giremez; yalnızca puantaj akışına yönlendirilir.
            from attendance.views import _unresolved_forgotten_checkout
            forgotten_record = _unresolved_forgotten_checkout(request.user)
            if forgotten_record and request.path not in self.STAFF_PRE_ATTENDANCE_PATHS:
                return redirect(reverse("attendance_scan"))

            if (not system.staff_access_enabled or staff_break_active()) and request.path not in self.STAFF_PRE_ATTENDANCE_PATHS:
                return redirect(reverse("attendance_scan"))

            active_record = AttendanceRecord.objects.filter(
                user=request.user,
                work_date=timezone.localdate(),
                status="worked",
                check_in__isnull=False,
                check_out__isnull=True,
            ).exists()

            if not active_record and request.path not in self.STAFF_PRE_ATTENDANCE_PATHS:
                return redirect(reverse("attendance_scan"))

            # Hafta içi 19:00-08:30 arasında, hafta sonu ise tüm gün
            # normal personel her yeni sayfa/QR geçişinde konumunu yeniden doğrulamalı.
            now_local = timezone.localtime()
            current_time = now_local.time().replace(tzinfo=None)
            after_hours = (
                now_local.weekday() >= 5
                or current_time >= time(19, 0)
                or current_time < time(8, 30)
            )
            if active_record and after_hours:
                if request.path not in self.STAFF_PRE_ATTENDANCE_PATHS:
                    one_request_ok = request.session.pop("moli_after_hours_one_request_ok", False)
                    if not one_request_ok:
                        # Yalnızca gerçek sayfa gezintileri dönüş adresini değiştirsin.
                        # favicon, service worker ve arka plan API istekleri kullanıcının
                        # gitmek istediği sayfayı ezmemeli.
                        fetch_dest = request.headers.get("Sec-Fetch-Dest", "")
                        accept = request.headers.get("Accept", "")
                        is_page_navigation = (
                            request.method == "GET"
                            and (
                                fetch_dest == "document"
                                or (not fetch_dest and "text/html" in accept)
                            )
                        )
                        if is_page_navigation:
                            request.session["moli_after_hours_next"] = request.get_full_path()
                            request.session.modified = True
                        return redirect(reverse("staff_after_hours_location_gate"))

        # Mesai başladıktan sonra mevcut MoliApp yetkileri aynen uygulanır.
        feature_key = feature_for_path(request.path)
        if feature_key and not has_feature_access(request.user, feature_key):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Bu işlem için yetkiniz yok.")

        return self.get_response(request)
