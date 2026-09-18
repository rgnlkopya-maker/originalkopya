from django.http import HttpResponseForbidden
from .access import has_access


def _restricted_personnel(user):
    return (
        user.groups.filter(name="personel").exists()
        and user.username.casefold() != "tahir"
    )


class MoliAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(request.user, 'is_authenticated', False):
            return self.get_response(request)

        path = request.path
        permission = None

        if _restricted_personnel(request.user):
            blocked_paths = {
                "/orders/print/",
                "/orders/label/print/",
                "/ajax/gecmis-fiyatlar/",
                "/musteri/new/",
                "/ajax/musteri/ekle/",
                "/ajax/musteri/pasif-yap/",
                "/ajax/beden/ekle/",
                "/ajax/beden/pasif-yap/",
                "/ajax/urun-kod/ekle/",
                "/ajax/urun-kod/tip-guncelle/",
                "/ajax/urun-kod/pasif-yap/",
                "/ajax/renk/ekle/",
                "/ajax/renk/pasif-yap/",
            }
            if path in blocked_paths or (
                path.startswith("/order/") and path.endswith("/cikti-alindi/")
            ):
                return HttpResponseForbidden("Bu işlem için yetkiniz yok.")

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
        elif path in {'/attendance/', '/attendance/punch/'}:
            permission = None
        elif path.startswith('/attendance/'):
            permission = 'can_view_attendance'
        elif path.startswith('/planlama/'):
            permission = 'can_manage_planning'
        elif path.startswith('/asistan/') or path.startswith('/api/assistant/'):
            permission = 'can_view_assistant'
        elif path.startswith('/kalite/'):
            permission = 'can_manage_quality'
        elif path.startswith('/depolar/'):
            permission = 'can_view_depots'
        elif path.startswith('/orders/export/excel/'):
            permission = 'can_create_orders'
        elif path.startswith('/order/new/') or path.startswith('/orders/multi-create/'):
            permission = 'can_create_orders'
        elif '/delete/' in path and path.startswith('/order/'):
            permission = 'can_delete_orders'
        elif path.startswith('/orders/') and '/update/' in path:
            permission = 'can_update_production'
        elif path.startswith('/order/') and path.endswith('/edit/'):
            permission = 'can_edit_orders'
        elif path == '/' or path.startswith('/order/'):
            permission = 'can_view_orders'

        if permission and not has_access(request.user, permission):
            return HttpResponseForbidden('Bu işlem için yetkiniz yok.')

        return self.get_response(request)
