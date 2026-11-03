"""Notification destinations and unread status for the manager inbox."""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from .models import Notification

_DESTINATIONS = {
    "Faturaya Aktarılmayan Yeni Sevkiyat": "/urun-kartlari/faturalar/aktarilmayan-sevkler/",
    "Fatura Aktarım Hatası": "/urun-kartlari/faturalar/",
    "Otomatik Yedekleme Başarısız": "/yonetim/yedekleme-merkezi/",
    "Güvenlik Uyarısı": "/sistem-sagligi/",
}

def destination_for(notification):
    if notification.order_id:
        return f"/order/{notification.order_id}/"
    return _DESTINATIONS.get(notification.title, "")

@login_required
def notification_list(request):
    records = list(Notification.objects.filter(user=request.user).order_by("-timestamp"))
    for record in records:
        record.destination = destination_for(record)
    return render(request, "notifications/list.html", {"notifications": records})

@login_required
def notification_unread_status(request):
    return JsonResponse({"unread": Notification.objects.filter(user=request.user, is_read=False).exists()})


@login_required
@require_POST
def notification_delete(request, notification_id):
    """A user can remove only their own notification."""
    item = get_object_or_404(Notification, pk=notification_id, user=request.user)
    item.delete()
    return redirect("notification_list")


@login_required
@require_POST
def notification_delete_all(request):
    """Clear the current user's inbox, never anybody else's."""
    Notification.objects.filter(user=request.user).delete()
    return redirect("notification_list")
