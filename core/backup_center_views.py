from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from .backup_center_models import BackupPolicy, BackupExecution
from .instrument_models import InstrumentBackupRun

RULES = {
    "folios": ["MoliApp föyleri PDF", "Yazdırma HTML kopyaları", "JSON veri yedekleri", "Orijinal föy fotoğrafları", "Yeni ve değişen dosyalar"],
    "instruments": ["Excel liste yedeği", "JSON veri yedeği", "Çek ve senet fotoğrafları", "Mevcut fotoğrafları tekrar yükleme"],
}

def manager(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists())

@login_required
def backup_center(request):
    if not manager(request.user):
        return HttpResponseForbidden("Yedekleme Merkezi yetkiniz yok.")
    policies = []
    for key, name in BackupPolicy.MODULES:
        policy, _ = BackupPolicy.objects.get_or_create(module=key)
        policies.append({"key": key, "name": name, "policy": policy, "rules": RULES[key]})
    history = list(BackupExecution.objects.all()[:30])
    return render(request, "core/backup_center.html", {
        "policies": policies,
        "history": history,
        "instrument_runs": InstrumentBackupRun.objects.all()[:10],
    })

@login_required
@require_POST
def backup_policy_update(request):
    if not manager(request.user):
        return HttpResponseForbidden("Yedekleme ayarı yetkiniz yok.")
    module = request.POST.get("module")
    frequency = request.POST.get("frequency")
    if module not in dict(BackupPolicy.MODULES) or frequency not in dict(BackupPolicy.FREQUENCIES):
        messages.error(request, "Geçersiz yedekleme ayarı.")
        return redirect("backup_center")
    try:
        hour = int(request.POST.get("hour", "3"))
        minute = int(request.POST.get("minute", "0"))
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError()
    except ValueError:
        messages.error(request, "Saat aralığı geçersiz.")
        return redirect("backup_center")
    BackupPolicy.objects.update_or_create(module=module, defaults={"frequency": frequency, "hour": hour, "minute": minute})
    messages.success(request, "Yedekleme tercihi kaydedildi. Otomatik zamanlayıcı henüz etkinleştirilmedi.")
    return redirect("backup_center")
