"""Mark a manager notification as handled only after its destination loads."""
from django.utils.deprecation import MiddlewareMixin
from .models import Notification
from .notification_inbox import destination_for


class NotificationDestinationReadMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        user = getattr(request, "user", None)
        if (not user or not user.is_authenticated or request.method != "GET"
                or response.status_code != 200):
            return response
        path = request.path
        if path.startswith("/notifications/") or path.startswith("/bildirim"):
            return response
        unread = Notification.objects.filter(user=user, is_read=False)
        matched = []
        for notice in unread:
            dest = destination_for(notice)
            if dest and (path == dest or (dest.endswith("/") and path.startswith(dest))):
                matched.append(notice.pk)
        if matched:
            Notification.objects.filter(user=user, is_read=False, pk__in=matched).update(is_read=True)
        return response
