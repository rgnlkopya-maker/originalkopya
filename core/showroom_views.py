"""Read-only, staff-only 3D showroom. No database writes or schema changes."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.http import require_GET
from app_settings.access import has_full_access


@login_required
@require_GET
def showroom(request):
    if not has_full_access(request.user):
        return HttpResponseForbidden("3D Showroom için yönetici yetkisi gerekiyor.")
    return render(request, "showroom/index.html")
