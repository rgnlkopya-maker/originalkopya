import json
import re
import unicodedata

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Sum
from django.shortcuts import redirect, render

from app_settings.models import SystemSettings
from .models import DepoStok


def _normalize_code(name):
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper()
    return value[:20] or "DEPO"


def _load_custom_depots(settings_obj):
    raw = (settings_obj.active_depots or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            result = []
            for item in data:
                if isinstance(item, dict) and item.get("code") and item.get("name"):
                    result.append({"code": str(item["code"]), "name": str(item["name"])})
            return result
    except Exception:
        pass
    return []


def _save_custom_depots(settings_obj, depots):
    settings_obj.active_depots = json.dumps(depots, ensure_ascii=False)
    settings_obj.save(update_fields=["active_depots", "updated_at"])


@login_required
def depo_ozet(request):
    settings_obj = SystemSettings.get_solo()
    can_manage = request.user.is_superuser or request.user.groups.filter(name__in=["patron", "mudur"]).exists()

    if request.method == "POST" and request.POST.get("action") == "add_depot":
        if not can_manage:
            messages.error(request, "Yeni depo ekleme yetkiniz yok.")
            return redirect("depo_ozet")

        depo_adi = (request.POST.get("depo_adi") or "").strip()
        if not depo_adi:
            messages.error(request, "Depo adı boş bırakılamaz.")
            return redirect("depo_ozet")

        if len(depo_adi) > 40:
            messages.error(request, "Depo adı en fazla 40 karakter olabilir.")
            return redirect("depo_ozet")

        custom = _load_custom_depots(settings_obj)
        existing_codes = set(DepoStok.objects.values_list("depo", flat=True).distinct())
        existing_codes.update(item["code"] for item in custom)

        code = _normalize_code(depo_adi)
        base = code
        i = 2
        while code in existing_codes:
            code = f"{base[:17]}_{i}"[:20]
            i += 1

        custom.append({"code": code, "name": depo_adi})
        _save_custom_depots(settings_obj, custom)
        messages.success(request, f"{depo_adi} deposu eklendi.")
        return redirect("depo_ozet")

    rows = list(
        DepoStok.objects.values("depo")
        .annotate(
            toplam_adet=Sum("adet"),
            kayit_sayisi=Count("id"),
            son_guncelleme=Max("eklenme_tarihi"),
        )
        .order_by("depo")
    )

    choice_labels = dict(DepoStok.DEPO_SECENEKLERI)
    custom = _load_custom_depots(settings_obj)
    custom_labels = {item["code"]: item["name"] for item in custom}

    seen = set()
    depolar = []
    for row in rows:
        code = row["depo"]
        row["depo_adi"] = custom_labels.get(code) or choice_labels.get(code) or code.replace("_", " ").title()
        depolar.append(row)
        seen.add(code)

    for item in custom:
        if item["code"] not in seen:
            depolar.append({
                "depo": item["code"],
                "depo_adi": item["name"],
                "toplam_adet": 0,
                "kayit_sayisi": 0,
                "son_guncelleme": None,
            })

    return render(request, "depolar/ozet.html", {
        "depolar": depolar,
        "can_manage_depots": can_manage,
    })
