"""Notification destinations and unread status for the manager inbox."""
import json
import re

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from .models import Notification, Order

_DESTINATIONS = {
    "Faturaya Aktarılmayan Yeni Sevkiyat": "/urun-kartlari/faturalar/aktarilmayan-sevkler/",
    "Fatura Aktarım Hatası": "/urun-kartlari/faturalar/",
    "Otomatik Yedekleme Başarısız": "/yonetim/yedekleme-merkezi/",
    "Güvenlik Uyarısı": "/sistem-sagligi/",
}

def destination_for(notification):
    explicit = (getattr(notification, "destination_url", "") or "").strip()
    if explicit.startswith("/") and not explicit.startswith("//"):
        return explicit
    if notification.order_id:
        return f"/order/{notification.order_id}/"
    return _DESTINATIONS.get(notification.title, "")

@login_required
def notification_list(request):
    records = list(Notification.objects.filter(user=request.user).order_by("-timestamp"))
    for record in records:
        record.destination = destination_for(record)
        record.stalled_rows = []
        record.stalled_summary = ""
        if record.title == "Üretim Aşaması Takıldı":
            message = record.message or ""
            match = re.match(r"^\[stalled-production:[^]]+\]\s*", message)
            content = message[match.end():] if match else message
            summary, sep, payload = content.partition("\nSTALLED_DETAILS:")
            record.stalled_summary = summary.split(": ", 1)[0] if not sep else summary
            if sep:
                try:
                    details = json.loads(payload)
                    if isinstance(details, list):
                        record.stalled_rows = [
                            {**row, "url": f"/order/{int(row['id'])}/"}
                            for row in details if isinstance(row, dict) and str(row.get("id", "")).isdigit()
                        ]
                except (ValueError, TypeError, KeyError):
                    pass
            else:
                # Historical notifications stored only the first eight order
                # numbers in plain text. Keep them usable without rewriting DB.
                nums = re.findall(r"([A-Z][A-Z0-9_-]+)\s*\((\d+) gün\)", content)
                orders = {
                    o.siparis_numarasi: o
                    for o in Order.objects.filter(siparis_numarasi__in=[number for number, _ in nums]).select_related("musteri")
                }
                for number, days in nums:
                    o = orders.get(number)
                    if o:
                        record.stalled_rows.append({
                            "number": number, "customer": o.musteri.ad if o.musteri else "Stok",
                            "product": o.urun_kodu or "", "color": o.renk or "",
                            "size": o.beden or "", "reference": o.musteri_referans or "",
                            "description": o.aciklama or "", "days": days,
                            "url": f"/order/{o.pk}/",
                        })
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
