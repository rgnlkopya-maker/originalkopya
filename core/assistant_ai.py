import os
import re
from datetime import timedelta
from decimal import Decimal

import requests
from django.db.models import OuterRef, Subquery, DateTimeField, Q
from django.utils import timezone

from .models import Order, OrderEvent
from .order_list_enhanced import STAGE_TRANSLATIONS


MAX_ORDER_ROWS = 80
MAX_HISTORY_ITEMS = 12


def _can(user, field):
    if user.is_superuser:
        return True
    access = getattr(user, "moli_access", None)
    return bool(access and getattr(access, field, False))


def _status_label(stage, value):
    if not stage or not value:
        return "-"
    return STAGE_TRANSLATIONS.get((stage, value), f"{stage}: {value}")


def _latest_event_subquery():
    return (
        OrderEvent.objects.filter(order=OuterRef("pk"))
        .exclude(event_type="order_update")
        .exclude(stage__in=["satis_fiyati", "ekstra_maliyet", "maliyet_override", "maliyet_uygulanan"])
        .order_by("-timestamp", "-id")
    )


def _targeted_orders(message):
    """Mesajda sipariş/model numarası görünüyorsa o kayıtlara ayrıca odaklan."""
    tokens = set(re.findall(r"\b[A-Za-zÇĞİÖŞÜçğıöşü]*\d{3,8}\b", message or ""))
    if not tokens:
        return Order.objects.none()
    q = Q()
    for token in tokens:
        q |= Q(siparis_numarasi__icontains=token) | Q(urun_kodu__icontains=token)
    return Order.objects.filter(q).select_related("musteri")[:25]


def build_moli_context(user, message):
    """Yalnızca SELECT sorguları ile okunabilir Moli bağlamı üretir."""
    today = timezone.localdate()
    can_orders = _can(user, "can_view_orders")
    can_finance = _can(user, "can_view_costs") or _can(user, "can_view_shipping_finance")

    if not can_orders:
        return "MOLI VERİ ERİŞİMİ: Bu kullanıcının sipariş verilerini görme yetkisi yok."

    latest = _latest_event_subquery()
    qs = (
        Order.objects.select_related("musteri")
        .annotate(
            latest_stage=Subquery(latest.values("stage")[:1]),
            latest_value=Subquery(latest.values("value")[:1]),
            latest_status_at=Subquery(latest.values("timestamp")[:1], output_field=DateTimeField()),
        )
        .order_by("-siparis_tarihi", "-id")
    )

    active = qs.filter(is_active=True)
    total_active = active.count()
    shipped = active.filter(latest_stage="sevkiyat_durum", latest_value="gonderildi").count()
    returned = active.filter(latest_stage="sevkiyat_durum", latest_value__in=["iade_geldi", "kargodan_geri_geldi"]).count()
    overdue = active.filter(teslim_tarihi__lt=today).exclude(latest_stage="sevkiyat_durum", latest_value="gonderildi").count()
    next_7 = active.filter(teslim_tarihi__range=[today, today + timedelta(days=7)]).count()

    lines = [
        "MOLI VERİLERİ (SALT OKUNUR):",
        f"Bugün: {today.isoformat()}",
        f"Aktif sipariş: {total_active}",
        f"Sevk edilmiş aktif kayıt: {shipped}",
        f"İade/kargodan geri gelen: {returned}",
        f"Planlanan teslim tarihi geçmiş ve henüz sevk edilmemiş: {overdue}",
        f"Önümüzdeki 7 günde planlanan teslim: {next_7}",
        "",
        f"Son {MAX_ORDER_ROWS} sipariş:",
    ]

    for o in active[:MAX_ORDER_ROWS]:
        customer = o.musteri.ad if o.musteri else "-"
        status = _status_label(o.latest_stage, o.latest_value)
        row = (
            f"- {o.siparis_numarasi} | müşteri={customer} | ürün={o.urun_kodu or '-'} | "
            f"tip={o.get_siparis_tipi_display() if o.siparis_tipi else '-'} | adet={o.adet or 0} | "
            f"sipariş_tarihi={o.siparis_tarihi or '-'} | planlanan_teslim={o.teslim_tarihi or '-'} | "
            f"son_durum={status}"
        )
        if o.latest_status_at:
            row += f" | son_durum_tarihi={timezone.localtime(o.latest_status_at).strftime('%Y-%m-%d %H:%M')}"
        if can_finance:
            sale = o.satis_fiyati if o.satis_fiyati is not None else "-"
            cost = o.toplam_maliyet if hasattr(o, "toplam_maliyet") else "-"
            row += f" | satış={sale} {o.para_birimi} | maliyet={cost} {o.maliyet_para_birimi}"
        lines.append(row)

    targeted = _targeted_orders(message)
    if targeted.exists():
        lines += ["", "Mesajla doğrudan eşleşen sipariş/model kayıtları:"]
        for o in targeted:
            customer = o.musteri.ad if o.musteri else "-"
            lines.append(
                f"- {o.siparis_numarasi} | müşteri={customer} | ürün={o.urun_kodu or '-'} | "
                f"tip={o.get_siparis_tipi_display() if o.siparis_tipi else '-'} | adet={o.adet or 0} | "
                f"sipariş={o.siparis_tarihi or '-'} | planlanan_teslim={o.teslim_tarihi or '-'}"
            )

    if not can_finance:
        lines += ["", "GİZLİLİK: Bu kullanıcının finans/maliyet yetkisi olmadığı için fiyat, maliyet ve kâr verileri bağlama dahil edilmedi."]

    return "\n".join(lines)


def _extract_text(result):
    candidates = result.get("candidates") or []
    if not candidates:
        return "Asistan şu anda cevap üretemedi."
    parts = (((candidates[0] or {}).get("content") or {}).get("parts") or [])
    texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
    return "\n".join(texts).strip() or "Asistan şu anda cevap üretemedi."


def ask_gemini(user, message, history):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY tanımlı değil.")

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    moli_context = build_moli_context(user, message)
    system_text = f"""
Sen MoliApp içindeki Moli Asistan'sın. Türkçe konuş. Kullanıcıyla doğal biçimde ekonomi, gündelik hayat,
üretim ve işletme hakkında sohbet edebilirsin. Sana aşağıda Moli'nin veritabanından yalnızca okunabilir
bir özet verilir. Bu verileri yorumlayabilir, karşılaştırabilir, risk ve gecikme işaretlerini söyleyebilir,
ama ASLA sipariş, maliyet, personel, puantaj, ayar veya başka bir veriyi değiştiremezsin. Kullanıcı senden
bir şeyi değiştirmeni isterse bunu yapamayacağını açıkça söyle ve yalnızca öneri ver. Veritabanına yazma,
silme, güncelleme veya işlem tetikleme yetkin yoktur.

Moli verileriyle ilgili bir cevap verirken sadece verilen bağlamdaki rakam ve kayıtları gerçek kabul et;
bağlamda olmayan şirket verisini uydurma. Güncel ekonomi, piyasa, kur, haber gibi zamana duyarlı bir soru
sorulursa web araması kullanman uygundur. Web bilgisi ile Moli iç verisini birbirine karıştırma; hangisinin
şirket verisi, hangisinin dış kaynak olduğunu net anlat.

KULLANICI: {user.get_full_name() or user.username}

{moli_context}
""".strip()

    contents = []
    for item in (history or [])[-MAX_HISTORY_ITEMS:]:
        role = "model" if item.get("role") == "assistant" else "user"
        text = (item.get("content") or "").strip()
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": message}]})

    payload = {
        "systemInstruction": {"parts": [{"text": system_text}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.45, "maxOutputTokens": 1200},
        "tools": [{"google_search": {}}],
    }

    response = requests.post(url, json=payload, timeout=45)
    result = response.json()

    # Bazı hesap/model kombinasyonlarında google_search açık olmayabilir; salt sohbeti yine çalıştır.
    if response.status_code >= 400 or result.get("error"):
        payload.pop("tools", None)
        response = requests.post(url, json=payload, timeout=45)
        result = response.json()

    if response.status_code >= 400 or result.get("error"):
        detail = (result.get("error") or {}).get("message") or f"HTTP {response.status_code}"
        raise RuntimeError(detail)

    return _extract_text(result)
