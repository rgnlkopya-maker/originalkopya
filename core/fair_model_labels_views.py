"""Fair mannequin model-code labels, separate from order/QR label printing."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from app_settings.access import has_full_access


@login_required
def fair_model_labels(request):
    if not has_full_access(request.user):
        return HttpResponseForbidden("Bu etiketleri hazırlama yetkiniz yok.")
    return render(request, "core/fair_model_labels.html")
