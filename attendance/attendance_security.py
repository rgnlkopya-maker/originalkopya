from time import time

from django.contrib.auth import authenticate
from django.http import HttpResponseForbidden, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse


class AttendancePasswordGateMiddleware:
    """Reuse Puantaj password verification for a fixed, five-minute window."""

    PREFIX = "/attendance/panel/"
    VERIFIED_SESSION_KEY = "_attendance_password_verified_user"
    VERIFIED_UNTIL_KEY = "_attendance_password_verified_until"
    WINDOW_SECONDS = 5 * 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if not path.startswith(self.PREFIX):
            return self.get_response(request)

        user = request.user
        if not user.is_authenticated:
            return self._uncached(self.get_response(request))

        gate_path = reverse("attendance_password_gate")
        if path == gate_path:
            return self._uncached(self._gate(request))

        until = request.session.get(self.VERIFIED_UNTIL_KEY)
        verified = (
            request.session.get(self.VERIFIED_SESSION_KEY) == user.pk
            and isinstance(until, (int, float))
            and until > time()
        )
        if verified:
            return self._uncached(self.get_response(request))

        request.session.pop(self.VERIFIED_SESSION_KEY, None)
        request.session.pop(self.VERIFIED_UNTIL_KEY, None)
        if request.method not in {"GET", "HEAD"}:
            # The UI can ask for re-verification without discarding the unsaved form.
            return self._uncached(JsonResponse({
                "ok": False,
                "message": "Puantaj doğrulaması sona erdi. Şifreyi doğrulayıp işlemi tekrar kaydedin.",
                "reauth_url": gate_path,
            }, status=403))

        request.session["_attendance_gate_next"] = request.get_full_path()
        return self._uncached(HttpResponseRedirect(gate_path))

    def _gate(self, request):
        from attendance.views import is_patron as has_full_access

        if not has_full_access(request.user):
            return HttpResponseForbidden("Puantaj erişim yetkiniz bulunmuyor.")

        error = ""
        if request.method == "POST":
            password = request.POST.get("password", "")
            confirmed = authenticate(request, username=request.user.get_username(), password=password)
            if confirmed is not None and confirmed.pk == request.user.pk:
                request.session[self.VERIFIED_SESSION_KEY] = request.user.pk
                destination = request.session.pop("_attendance_gate_next", None) or reverse("attendance_dashboard")
                if not destination.startswith(self.PREFIX) or destination == reverse("attendance_password_gate"):
                    destination = reverse("attendance_dashboard")
                request.session[self.VERIFIED_UNTIL_KEY] = time() + self.WINDOW_SECONDS
                return HttpResponseRedirect(destination)
            error = "Şifre yanlış. Lütfen tekrar deneyin."
        return render(request, "attendance_v2/attendance_password_gate.html", {"error": error})

    @staticmethod
    def _uncached(response):
        response["Cache-Control"] = "private, no-store, no-cache, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response
