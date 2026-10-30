from urllib.parse import urlsplit
from django.utils import timezone

from django.conf import settings
from django.contrib.auth import authenticate
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache


class SalaryPasswordGateMiddleware:
    """Require the signed-in user's password when entering the salary area.

    Internal navigation remains unlocked; a fresh external/deep-link entry
    requires re-verification. Sensitive pages are never browser-cached.
    """

    PREFIX = "/attendance/maaslar/"
    VERIFIED_SESSION_KEY = "_salary_password_verified_user"
    HANDOFF_KEY = "_salary_gate_handoff"
    ACTIVITY_KEY = "_salary_last_activity"
    IDLE_SECONDS = 300

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if not path.startswith(self.PREFIX):
            if request.user.is_authenticated and request.method == "GET" and (
                request.META.get("HTTP_SEC_FETCH_DEST") == "document"
                or (request.META.get("HTTP_ACCEPT", "").startswith("text/html")
                    and request.META.get("HTTP_X_REQUESTED_WITH") != "XMLHttpRequest")
            ):
                request.session.pop(self.VERIFIED_SESSION_KEY, None)
                request.session.pop(self.HANDOFF_KEY, None)
                request.session.pop(self.ACTIVITY_KEY, None)
            return self.get_response(request)

        user = request.user
        if not user.is_authenticated:
            return self._uncached(self.get_response(request))

        from app_settings.access import has_full_access
        if not has_full_access(user):
            return self._uncached(HttpResponseForbidden("Maaş Yönetimi erişim yetkiniz bulunmuyor."))
        gate_path = reverse("salary_password_gate")
        if path == gate_path:
            return self._uncached(self._gate(request))

        # An internal salary navigation may reuse the verification, but
        # entering from elsewhere (including a direct bookmark) cannot.
        referrer = request.META.get("HTTP_REFERER", "")
        ref_path = urlsplit(referrer).path if referrer else ""
        trusted_referrer = bool(referrer and url_has_allowed_host_and_scheme(
            referrer, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ))
        internal_navigation = trusted_referrer and ref_path.startswith(self.PREFIX)
        verified = request.session.get(self.VERIFIED_SESSION_KEY) == user.pk
        now = timezone.now().timestamp()
        last_activity = request.session.get(self.ACTIVITY_KEY)
        if not isinstance(last_activity, (int, float)) or now - last_activity >= self.IDLE_SECONDS:
            verified = False

        handoff = request.session.pop(self.HANDOFF_KEY, None)
        from_gate = handoff == request.get_full_path()
        forced_reauth = request.GET.get("salary_reauth") == "1"
        if not verified or forced_reauth or (
            request.method == "GET" and not internal_navigation and not from_gate
        ):
            request.session.pop(self.VERIFIED_SESSION_KEY, None)
            request.session.pop(self.ACTIVITY_KEY, None)
            if request.method != "GET":
                return self._uncached(HttpResponseRedirect(gate_path))
            request.session["_salary_gate_next"] = request.get_full_path()
            return self._uncached(HttpResponseRedirect(gate_path))

        # Ignore background polling for the five-minute inactivity clock.
        if request.method != "GET" or "text/html" in request.META.get("HTTP_ACCEPT", "") and request.META.get("HTTP_X_REQUESTED_WITH") != "XMLHttpRequest":
            request.session[self.ACTIVITY_KEY] = now
        return self._uncached(self.get_response(request))

    def _gate(self, request):
        from app_settings.access import has_full_access

        if not has_full_access(request.user):
            return HttpResponseForbidden("Maaş Yönetimi erişim yetkiniz bulunmuyor.")

        error = ""
        if request.method == "POST":
            password = request.POST.get("password", "")
            confirmed = authenticate(request, username=request.user.get_username(), password=password)
            if confirmed is not None and confirmed.pk == request.user.pk:
                request.session[self.VERIFIED_SESSION_KEY] = request.user.pk
                request.session[self.ACTIVITY_KEY] = timezone.now().timestamp()
                destination = request.session.pop("_salary_gate_next", None) or reverse("salary_home")
                if not destination.startswith(self.PREFIX) or destination == reverse("salary_password_gate"):
                    destination = reverse("salary_home")
                request.session[self.HANDOFF_KEY] = destination
                return HttpResponseRedirect(destination)
            error = "Şifre yanlış. Lütfen tekrar deneyin."
        return render(request, "attendance_v2/salary_password_gate.html", {"error": error})

    @staticmethod
    def _uncached(response):
        response["Cache-Control"] = "private, no-store, no-cache, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response
