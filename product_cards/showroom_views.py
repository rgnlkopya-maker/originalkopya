from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render


def _manager(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


def _allowed(user):
    access = getattr(user, "moli_access", None)
    return _manager(user) or bool(access and access.can_create_orders)


@login_required
def showroom_page(request):
    if not _allowed(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    return render(request, "product_cards/showroom_draft.html")
