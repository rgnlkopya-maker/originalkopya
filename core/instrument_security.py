"""Require current signed-in account password for each entry to cheque/senet pages."""
from urllib.parse import urlsplit
from django.utils import timezone

from django.contrib.auth import authenticate
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


class InstrumentPasswordGateMiddleware:
    PREFIX = "/muhasebe/cek-senet/"
    VERIFIED = "_instrument_password_verified_user"
    HANDOFF = "_instrument_password_handoff"
    ACTIVITY = "_instrument_last_activity"
    IDLE_SECONDS = 300
    NEXT = "_instrument_password_next"

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
                request.session.pop(self.VERIFIED, None)
                request.session.pop(self.HANDOFF, None)
                request.session.pop(self.ACTIVITY, None)
            return self.get_response(request)

        user = request.user
        if not user.is_authenticated:
            return self._uncached(self.get_response(request))

        if not (user.is_superuser or user.groups.filter(name__in=("patron", "mudur")).exists()):
            return self._uncached(HttpResponseForbidden("Çek/Senet erişim yetkiniz bulunmuyor."))

        gate_path = reverse("instrument_password_gate")
        if path == gate_path:
            return self._uncached(self._gate(request))

        # Preserve Google's OAuth callback; it validates its own session state.
        if path == reverse("instrument_drive_callback"):
            return self._uncached(self.get_response(request))

        referrer = request.META.get("HTTP_REFERER", "")
        trusted = bool(referrer and url_has_allowed_host_and_scheme(
            referrer, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ))
        internal = trusted and urlsplit(referrer).path.startswith(self.PREFIX)
        verified = request.session.get(self.VERIFIED) == user.pk
        now = timezone.now().timestamp()
        last_activity = request.session.get(self.ACTIVITY)
        if not isinstance(last_activity, (int, float)) or now - last_activity >= self.IDLE_SECONDS:
            verified = False
        handoff = request.session.pop(self.HANDOFF, None)
        from_gate = handoff == request.get_full_path()

        if not verified or (not internal and not from_gate):
            request.session.pop(self.VERIFIED, None)
            request.session.pop(self.ACTIVITY, None)
            if request.method != "GET":
                return self._uncached(HttpResponseRedirect(gate_path))
            request.session[self.NEXT] = request.get_full_path()
            return self._uncached(HttpResponseRedirect(gate_path))

        # Explicit user-activity heartbeat; authenticated, same-section and CSRF checked.
        if path == self.PREFIX + "_activity/":
            if request.method != "POST":
                return self._uncached(HttpResponse(status=405))
            request.session[self.ACTIVITY] = now
            return self._uncached(HttpResponse(status=204))

        # Ignore background polling for the five-minute inactivity clock.
        if request.method != "GET" or "text/html" in request.META.get("HTTP_ACCEPT", "") and request.META.get("HTTP_X_REQUESTED_WITH") != "XMLHttpRequest":
            request.session[self.ACTIVITY] = now
        return self._uncached(self.get_response(request))

    def _gate(self, request):
        error = ""
        if request.method == "POST":
            password = request.POST.get("password", "")
            user = authenticate(request, username=request.user.get_username(), password=password)
            if user is not None and user.pk == request.user.pk:
                request.session[self.VERIFIED] = user.pk
                request.session[self.ACTIVITY] = timezone.now().timestamp()
                destination = request.session.pop(self.NEXT, None) or reverse("instrument_list")
                if not destination.startswith(self.PREFIX) or destination == reverse("instrument_password_gate"):
                    destination = reverse("instrument_list")
                request.session[self.HANDOFF] = destination
                return HttpResponseRedirect(destination)
            error = "Şifre yanlış. Lütfen tekrar deneyin."
        return render(request, "core/instrument_password_gate.html", {"error": error})

    @staticmethod
    def _uncached(response):
        response["Cache-Control"] = "private, no-store, no-cache, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response
