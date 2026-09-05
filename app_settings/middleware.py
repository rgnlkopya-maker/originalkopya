from django.http import HttpResponseForbidden
from .access import has_access


class MoliAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(request.user, 'is_authenticated', False):
            return self.get_response(request)

        path = request.path
        permission = None

        if path.startswith('/ayarlar/'):
            permission = 'can_view_settings'
        elif path.startswith('/users/'):
            permission = 'can_manage_users'
        elif path.startswith('/reports/sevkiyat-finans/'):
            permission = 'can_view_shipping_finance'
        elif path.startswith('/reports/personel/') or path.startswith('/kalite/personel/'):
            permission = 'can_view_personnel'
        elif path.startswith('/reports/'):
            permission = 'can_view_reports'
        elif path.startswith('/product-costs/') or path.startswith('/urun-kartlari/'):
            permission = 'can_view_costs'
        elif path.startswith('/attendance/'):
            permission = 'can_view_attendance'
        elif path.startswith('/asistan/') or path.startswith('/api/assistant/'):
            permission = 'can_view_assistant'
        elif path.startswith('/kalite/'):
            permission = 'can_manage_quality'
        elif path.startswith('/depolar/'):
            permission = 'can_view_depots'
        elif path.startswith('/order/new/') or path.startswith('/orders/multi-create/'):
            permission = 'can_create_orders'
        elif '/delete/' in path and path.startswith('/order/'):
            permission = 'can_delete_orders'
        elif path.startswith('/orders/') and '/update/' in path:
            permission = 'can_edit_orders'
        elif path.startswith('/order/') and path.endswith('/edit/'):
            permission = 'can_edit_orders'
        elif path == '/' or path.startswith('/order/'):
            permission = 'can_view_orders'

        if permission and not has_access(request.user, permission):
            return HttpResponseForbidden('Bu işlem için yetkiniz yok.')

        return self.get_response(request)
