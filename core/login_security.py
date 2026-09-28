import hashlib

from django.core.cache import cache


MAX_FAILED_ATTEMPTS = 5
LOCK_SECONDS = 10 * 60
WINDOW_SECONDS = 10 * 60


def _digest(value):
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:24]


def _client_ip(request):
    # Render/Django tarafinda baglanan istemci adresini kullan.
    return (request.META.get("REMOTE_ADDR") or "unknown").strip()


def _keys(request, username):
    username_key = f"login-fail-user:{_digest((username or '').strip().lower())}"
    ip_key = f"login-fail-ip:{_digest(_client_ip(request))}"
    return username_key, ip_key


def login_lock_status(request, username):
    username_key, ip_key = _keys(request, username)
    user_count = int(cache.get(username_key, 0) or 0)
    ip_count = int(cache.get(ip_key, 0) or 0)
    locked = user_count >= MAX_FAILED_ATTEMPTS or ip_count >= MAX_FAILED_ATTEMPTS
    return locked, max(user_count, ip_count)


def register_login_failure(request, username):
    counts = []
    for key in _keys(request, username):
        if cache.add(key, 1, timeout=WINDOW_SECONDS):
            count = 1
        else:
            try:
                count = cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=WINDOW_SECONDS)
                count = 1
        counts.append(count)
        if count >= MAX_FAILED_ATTEMPTS:
            # Esik asildiginda kilit en az 10 dakika sursun.
            cache.set(key, count, timeout=LOCK_SECONDS)
    return max(counts)


def clear_login_failures(request, username):
    username_key, ip_key = _keys(request, username)
    cache.delete_many([username_key, ip_key])
