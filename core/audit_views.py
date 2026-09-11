from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from .models import AuditLog


User = get_user_model()


def _is_manager(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


@login_required
def employee_audit_logs(request, user_id):
    if not _is_manager(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    employee = get_object_or_404(User, pk=user_id)
    logs = AuditLog.objects.filter(user=employee)
    query = (request.GET.get("q") or "").strip()
    action = (request.GET.get("action") or "").strip()
    start = (request.GET.get("start") or "").strip()
    end = (request.GET.get("end") or "").strip()

    if query:
        logs = logs.filter(
            Q(action__icontains=query)
            | Q(object_ref__icontains=query)
            | Q(path__icontains=query)
        )
    if action:
        logs = logs.filter(action=action)
    try:
        if start:
            logs = logs.filter(created_at__date__gte=date.fromisoformat(start))
        if end:
            logs = logs.filter(created_at__date__lte=date.fromisoformat(end))
    except ValueError:
        pass

    action_choices = (
        AuditLog.objects.filter(user=employee)
        .order_by("action")
        .values_list("action", flat=True)
        .distinct()
    )
    page = Paginator(logs, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "teams/employee_audit_logs.html",
        {
            "employee": employee,
            "page": page,
            "action_choices": action_choices,
            "q": query,
            "selected_action": action,
            "start": start,
            "end": end,
        },
    )
