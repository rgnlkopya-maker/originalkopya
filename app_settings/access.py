from functools import wraps
from django.http import HttpResponseForbidden
from .models import UserAccess


FULL_ACCESS_GROUPS = {"patron", "mudur"}


def get_access(user):
    if not getattr(user, 'is_authenticated', False):
        return None
    access, _ = UserAccess.objects.get_or_create(user=user)
    return access


def has_full_access(user):
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=FULL_ACCESS_GROUPS).exists()


def has_access(user, permission_name):
    if not getattr(user, 'is_authenticated', False):
        return False
    if has_full_access(user):
        return True
    access = get_access(user)
    return bool(getattr(access, permission_name, False))


def access_required(permission_name):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not has_access(request.user, permission_name):
                return HttpResponseForbidden('Bu bölüme erişim yetkiniz yok.')
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
