import os
import re
from datetime import date, datetime, timedelta
from decimal import Decimal

import requests
from django.apps import apps
from django.db import models
from django.db.models import OuterRef, Subquery, DateTimeField, Q
from django.utils import timezone

from .models import Order, OrderEvent
from .order_list_enhanced import STAGE_TRANSLATIONS

MAX_ORDER_ROWS = 80
MAX_HISTORY_ITEMS = 12
MAX_MODEL_ROWS = 30
MAX_TARGET_ROWS = 50
MAX_VALUE_CHARS = 220

# Django altyapı tabloları şirket verisi değildir. Yeni Moli uygulamaları/model tabloları ise
# otomatik olarak keşfedilir ve salt okunur bağlama dahil edilir.
EXCLUDED_APP_LABELS = {"admin", "contenttypes", "sessions", "messages", "staticfiles"}
SENSITIVE_FIELD_PARTS = {
    "password", "passwd", "secret", "token", "api_key", "apikey", "private_key",
    "session_data", "auth_key", "access_key", "refresh_token",
}


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
    tokens = set(re.findall(r"\b[A-Za-zÇĞİÖŞÜçğıöşü]*\d{3,8}\b", message or ""))
    if not tokens:
        return Order.objects.none()
    q = Q()
    for token in tokens:
        q |= Q(siparis_numarasi__icontains=token) | Q(urun_kodu__icontains=token)
    return Order.objects.filter(q).select_related("musteri")[:25]


def _is_sensitive_field(field_name):
    name = (field_name or "").lower()
    return any(part in name for part in SENSITIVE_FIELD_PARTS)


def _safe_value(value):
    if value is None:
        return "-"
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    if len(text) > MAX_VALUE_CHARS:
        text = text[:MAX_VALUE_CHARS] + "…"
    return text or "-"


def _business_models():
    """Moli'nin mevcut ve gelecekte eklenecek iş modellerini otomatik keşfet."""
    discovered = []
    for model in apps.get_models():
        meta = model._meta
        if meta.proxy or meta.abstract or meta.app_label in EXCLUDED_APP_LABELS:
            continue
        # Django auth kullanıcısını personel bağlantıları için okuyabiliriz; izin/grup tablolarını bağlama taşımıyoruz.
        if meta.app_label == "auth" and model.__name__ not in {"User"}:
            continue
        discovered.append(model)
    return discovered


def _readable_fields(model):
    fields = []
    for field in model._meta.concrete_fields:
        if _is_sensitive_field(field.name):
            continue
        if isinstance(field, (models.BinaryField, models.FileField, models.ImageField)):
            continue
        fields.append(field)
    return fields


def _model_keywords(model):
    parts = {
        model.__name__, model._meta.model_name, model._meta.verbose_name,
        model._meta.verbose_name_plural, model._meta.app_label,
    }
    for field in _readable_fields(model):
        parts.add(field.name)
        if getattr(field, "verbose_name", None):
            parts.add(str(field.verbose_name))
    return " ".join(str(x) for x in parts if x).lower()


def _relevance_score(model, message):
    msg = (message or "").lower()
    if not msg:
        return 0
    words = [w for w in re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9_]+", msg) if len(w) >= 3]
    haystack = _model_keywords(model)
    score = sum(3 for w in words if w in haystack)

    aliases = {
        "personel": ["user", "profile", "employee", "attendance", "mesai", "qualityissue"],
        "puantaj": ["attendance", "mesai"],
        "izin": ["attendance", "employee"],
        "hata": ["quality", "issue"],
        "fason": ["fasoncu", "orderevent"],
        "nakış": ["nakisci", "orderevent"],
        "nakis": ["nakisci", "orderevent"],
        "depo": ["depo", "stok"],
        "maliyet": ["cost", "order", "productcost"],
        "sipariş": ["order", "must"],
        "siparis": ["order", "must"],
        "müşteri": ["musteri", "order"],
        "musteri": ["musteri", "order"],
    }
    model_name = f"{model._meta.app_label}.{model.__name__}".lower()
    for trigger, targets in aliases.items():
        if trigger in msg and any(t in model_name for t in targets):
            score += 8
    return score


def _object_line(obj, fields):
    parts = [f"id={getattr(obj, 'pk', '-')}" ]
    for field in fields:
        if field.primary_key:
            continue
        try:
            if field.is_relation and isinstance(field, (models.ForeignKey, models.OneToOneField)):
                rel_obj = getattr(obj, field.name, None)
                value = f"{getattr(obj, field.attname, None) or '-'} ({_safe_value(rel_obj)})" if rel_obj else "-"
            else:
                value = getattr(obj, field.name, None)
            parts.append(f"{field.name}={_safe_value(value)}")
        except Exception:
            continue
    return " | ".join(parts)


def _target_filter(model, message):
    """Mesajdaki anlamlı kelime/numaraları modelin metin ve sayısal alanlarında salt okunur ara."""
    tokens = [t for t in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9_.+-]+", message or "") if len(t) >= 3][:8]
    if not tokens:
        return None
    q = Q()
    usable = False
    for field in _readable_fields(model):
        if field.is_relation:
            continue
        if isinstance(field, (models.CharField, models.TextField, models.EmailField)):
            for token in tokens:
                q |= Q(**{f"{field.name}__icontains": token})
                usable = True
        elif isinstance(field, (models.IntegerField, models.BigIntegerField, models.PositiveIntegerField, models.AutoField, models.BigAutoField)):
            for token in tokens:
                if token.isdigit():
                    q |= Q(**{field.name: int(token)})
                    usable = True
    return q if usable else None


def _dynamic_business_context(message):
    models_found = _business_models()
    scored = sorted(((m, _relevance_score(m, message)) for m in models_found), key=lambda x: (-x[1], x[0]._meta.label))

    lines = ["", "MOLI GENEL VERİ KATALOĞU (SALT OKUNUR):"]
    for model, _score in scored:
        try:
            count = model._default_manager.count()
        except Exception:
            continue
        field_names = [f.name for f in _readable_fields(model)]
        lines.append(f"- {model._meta.label}: {count} kayıt | alanlar={', '.join(field_names)}")

    relevant = [m for m, score in scored if score > 0][:8]
    if not relevant:
        relevant = [m for m, _score in scored[:5]]

    lines += ["", "SORUYLA İLGİLİ VERİLER:"]
    for model in relevant:
        fields = _readable_fields(model)
        try:
            manager = model._default_manager.all()
            target_q = _target_filter(model, message)
            if target_q is not None:
                matched = manager.filter(target_q).distinct()[:MAX_TARGET_ROWS]
                matched_items = list(matched)
            else:
                matched_items = []

            if matched_items:
                items = matched_items
                mode = "eşleşen"
            else:
                order_field = None
                field_names = {f.name for f in fields}
                for candidate in ("updated_at", "created_at", "timestamp", "work_date", "siparis_tarihi", "id"):
                    if candidate in field_names or candidate == "id":
                        order_field = candidate
                        break
                qs = manager.order_by(f"-{order_field}") if order_field else manager
                items = list(qs[:MAX_MODEL_ROWS])
                mode = "son"

            lines.append(f"\n[{model._meta.label}] {mode} {len(items)} kayıt:")
            for obj in items:
                lines.append("- " + _object_line(obj, fields))
        except Exception as exc:
            lines.append(f"\n[{model._meta.label}] okunamadı: {exc.__class__.__name__}")

    return "\n".join(lines)


def build_moli_context(user, message):
    """Moli veritabanını yalnızca SELECT sorguları ile okur; hiçbir yazma işlemi içermez."""
    today = timezone.localdate()
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
    lines = [
        "MOLI VERİLERİ (SALT OKUNUR / TAM İŞ VERİSİ ERİŞİMİ):",
        f"Bugün: {today.isoformat()}",
        f"Aktif sipariş: {active.count()}",
        f"Sevk edilmiş aktif kayıt: {active.filter(latest_stage='sevkiyat_durum', latest_value='gonderildi').count()}",
        f"İade/kargodan geri gelen: {active.filter(latest_stage='sevkiyat_durum', latest_value__in=['iade_geldi', 'kargodan_geri_geldi']).count()}",
        f"Teslim tarihi geçmiş ve sevk edilmemiş: {active.filter(teslim_tarihi__lt=today).exclude(latest_stage='sevkiyat_durum', latest_value='gonderildi').count()}",
        f"Önümüzdeki 7 günde planlanan teslim: {active.filter(teslim_tarihi__range=[today, today + timedelta(days=7)]).count()}",
        "",
        f"Son {MAX_ORDER_ROWS} aktif sipariş:",
    ]

    for o in active[:MAX_ORDER_ROWS]:
        customer = o.musteri.ad if o.musteri else "-"
        row = (
            f"- {o.siparis_numarasi} | müşteri={customer} | ürün={o.urun_kodu or '-'} | "
            f"ürün_tipi={o.get_urun_tipi_display() if o.urun_tipi else '-'} | "
            f"sipariş_tipi={o.get_siparis_tipi_display() if o.siparis_tipi else '-'} | adet={o.adet or 0} | "
            f"renk={o.renk or '-'} | beden={o.beden or '-'} | referans={o.musteri_referans or '-'} | "
            f"sipariş_tarihi={o.siparis_tarihi or '-'} | teslim={o.teslim_tarihi or '-'} | "
            f"son_durum={_status_label(o.latest_stage, o.latest_value)} | "
            f"satış={o.satis_fiyati if o.satis_fiyati is not None else '-'} {o.para_birimi} | "
            f"maliyet={o.toplam_maliyet if hasattr(o, 'toplam_maliyet') else '-'} {o.maliyet_para_birimi}"
        )
        lines.append(row)

    targeted = _targeted_orders(message)
    if targeted.exists():
        lines += ["", "Mesajla doğrudan eşleşen sipariş/model kayıtları:"]
        for o in targeted:
            lines.append(
                f"- {o.siparis_numarasi} | müşteri={o.musteri.ad if o.musteri else '-'} | ürün={o.urun_kodu or '-'} | "
                f"adet={o.adet or 0} | renk={o.renk or '-'} | beden={o.beden or '-'} | "
                f"sipariş={o.siparis_tarihi or '-'} | teslim={o.teslim_tarihi or '-'}"
            )

    lines.append(_dynamic_business_context(message))
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
Sen MoliApp içindeki Moli Asistan'sın. Türkçe konuş.

MoliApp veritabanındaki iş verilerine GENİŞ SALT OKUNUR erişimin vardır. Sana her soruda mevcut veri
kataloğu, model alanları ve soruyla ilgili kayıtlar sağlanır. Yeni MoliApp modelleri eklendiğinde bunlar da
otomatik olarak veri kataloğuna dahil edilir. Veriyi analiz edebilir, sayabilir, karşılaştırabilir, özetleyebilir,
risk/gecikme/hata eğilimleri çıkarabilir ve öneri sunabilirsin.

KESİN KURAL: Hiçbir koşulda veri oluşturamaz, değiştiremez, silemez veya uygulamada işlem tetikleyemezsin.
Sipariş durumu değiştirme, personel düzenleme, puantaj yazma, maliyet değiştirme, kullanıcı oluşturma,
fason/nakış hareketi kaydetme, ayar değiştirme dahil hiçbir yazma yetkin yoktur. Kullanıcı böyle bir işlem
isterse yapamayacağını söyle; istenirse nasıl yapılacağını anlatabilirsin. Sana sağlanan veri katmanı yalnızca
SELECT/okuma sorguları kullanır.

Şifre, token, API anahtarı ve benzeri teknik sırlar veri bağlamına dahil edilmez. Bağlamda olmayan şirket
verisini uydurma. Büyük veri kümelerinde sana tüm satırlar aynı anda gönderilmeyebilir; katalogdaki kayıt
sayılarını ve soruyla ilgili getirilen kayıtları temel al. Gereken veri bağlamda görünmüyorsa bunu açıkça söyle.

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
        "generationConfig": {"temperature": 0.35, "maxOutputTokens": 1600},
        "tools": [{"google_search": {}}],
    }

    response = requests.post(url, json=payload, timeout=45)
    result = response.json()
    if response.status_code >= 400 or result.get("error"):
        payload.pop("tools", None)
        response = requests.post(url, json=payload, timeout=45)
        result = response.json()
    if response.status_code >= 400 or result.get("error"):
        detail = (result.get("error") or {}).get("message") or f"HTTP {response.status_code}"
        raise RuntimeError(detail)
    return _extract_text(result)
