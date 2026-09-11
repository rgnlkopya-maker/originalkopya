import ipaddress
import re

from django.db import OperationalError, ProgrammingError

from .models import AuditLog


SENSITIVE_PARTS = {
    "password", "parola", "csrf", "token", "secret", "api_key",
    "latitude", "longitude", "konum",
}
MUTATING_GET_MARKERS = (
    "/update/",
    "/delete/",
    "/delete-image-by-url/",
    "/cikti-alindi/",
    "/toggle-active/",
)


def _should_log(request):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        return True
    return request.method == "GET" and any(marker in request.path for marker in MUTATING_GET_MARKERS)


def _safe_payload(request):
    if request.path in {"/attendance/punch/", "/login/", "/custom-login/"}:
        return {}
    payload = {}
    for key in request.POST.keys():
        if any(part in key.lower() for part in SENSITIVE_PARTS):
            continue
        values = request.POST.getlist(key)
        cleaned = [str(value)[:300] for value in values[:10]]
        payload[key] = cleaned[0] if len(cleaned) == 1 else cleaned
    if request.FILES:
        payload["uploaded_files"] = [
            {"field": key, "count": len(request.FILES.getlist(key))}
            for key in request.FILES.keys()
        ]
    return payload


def _action_label(path):
    rules = (
        ("/login", "Oturum açma denemesi"),
        ("/logout", "Oturumu kapattı"),
        ("/attendance/punch/", "Puantaj giriş/çıkış işlemi"),
        ("/production-transfer/", "Üretim geçmişini aktardı"),
        ("/stok-ekle/", "Siparişi stoğa aktardı"),
        ("/delete-image", "Sipariş görselini sildi"),
        ("/images/", "Sipariş görseli işlemi"),
        ("/delete/", "Kayıt silme işlemi"),
        ("/update/", "Üretim durumunu güncelledi"),
        ("/edit/", "Kayıt bilgilerini düzenledi"),
        ("/users/", "Personel/kullanıcı işlemi"),
        ("/urun-kartlari/", "Ürün veya malzeme kartı işlemi"),
        ("/product-costs/", "Maliyet işlemi"),
        ("/finance/", "Finans hareketi"),
        ("/planlama/", "Planlama işlemi"),
        ("/depolar/", "Depo/stok işlemi"),
        ("/kalite/", "Kalite kaydı işlemi"),
        ("/musteri/", "Müşteri kaydı işlemi"),
    )
    for marker, label in rules:
        if marker in path:
            return label
    return "Uygulama verisi değişikliği"


def _object_ref(request):
    patterns = (
        (r"/order/(\d+)/", "Sipariş"),
        (r"/orders/(\d+)/", "Sipariş"),
        (r"/users/(\d+)/", "Personel"),
        (r"/images/(\d+)/", "Görsel"),
        (r"/events/(\d+)/", "Üretim kaydı"),
    )
    for pattern, label in patterns:
        match = re.search(pattern, request.path)
        if match:
            return f"{label} #{match.group(1)}"
    for key, label in (("order_id", "Sipariş"), ("user_id", "Personel"), ("id", "Kayıt")):
        value = request.POST.get(key)
        if value and str(value).isdigit():
            return f"{label} #{value}"
    return ""


def _client_ip(request):
    raw = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    raw = raw or (request.META.get("REMOTE_ADDR") or "").strip()
    try:
        return str(ipaddress.ip_address(raw)) if raw else None
    except ValueError:
        return None


class UserActionAuditMiddleware:
    """Important state-changing requests are recorded without passwords or file contents."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        should_log = _should_log(request)
        payload = _safe_payload(request) if should_log else {}
        response = self.get_response(request)

        if should_log:
            try:
                user = request.user if getattr(request.user, "is_authenticated", False) else None
                username = user.username if user else (request.POST.get("username") or "")[:150]
                AuditLog.objects.create(
                    user=user,
                    username_snapshot=username,
                    action=_action_label(request.path),
                    method=request.method,
                    path=request.path[:500],
                    object_ref=_object_ref(request),
                    details={"payload": payload} if payload else {},
                    ip_address=_client_ip(request),
                    user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:500],
                    status_code=getattr(response, "status_code", 500),
                    success=getattr(response, "status_code", 500) < 400,
                )
            except (OperationalError, ProgrammingError):
                pass

        return response
