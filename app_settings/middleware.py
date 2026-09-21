from django.shortcuts import redirect
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
        "/logout/",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(request.user, "is_authenticated", False):
            return self.get_response(request)

        # Patron/Müdür mevcut tam erişim davranışını aynen korur.
        if not has_full_access(request.user):
            from attendance.models import AttendanceRecord
            from .models import SystemSettings

            system = SystemSettings.get_solo()
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

        # Mesai başladıktan sonra mevcut MoliApp yetkileri aynen uygulanır.
        feature_key = feature_for_path(request.path)
        if feature_key and not has_feature_access(request.user, feature_key):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Bu işlem için yetkiniz yok.")

        return self.get_response(request)
