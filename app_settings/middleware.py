from django.http import HttpResponseForbidden

from .access import has_feature_access
from .permission_registry import feature_for_path


class MoliAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(request.user, "is_authenticated", False):
            return self.get_response(request)

        feature_key = feature_for_path(request.path)
        if feature_key and not has_feature_access(request.user, feature_key):
            return HttpResponseForbidden("Bu işlem için yetkiniz yok.")

        return self.get_response(request)
