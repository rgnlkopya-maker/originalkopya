"""Deterministic, read-only full-history order analytics for Moli Asistan.

Never generate SQL from model output; all queries use Django ORM.
"""
import re
from django.db.models import Count, Sum, Q
from django.db.models.functions import ExtractYear
from app_settings.access import has_access, data_scope_value
from core.models import Order

MAX_GROUPS = 25


def order_analysis(user, question):
    if not has_access(user, "can_view_orders"):
        return "SIPARIS ANALIZI: Kullanıcının sipariş görme yetkisi yok."
    qs = Order.objects.all()
    if data_scope_value(user, "orders") == "active_only":
        qs = qs.filter(is_active=True)
    words = re.findall(r"(?<!\w)[A-Za-z0-9_-]*\d{3,8}[A-Za-z0-9_-]*(?!\w)", question or "")
    years = sorted({int(w) for w in words if w.isdecimal() and 2000 <= int(w) <= 2100})
    words = [w for w in words if not (w.isdecimal() and 2000 <= int(w) <= 2100)]
    if words:
        terms = words[:4]
        condition = Q()
        for word in terms:
            condition |= Q(urun_kodu__iexact=word) | Q(siparis_numarasi__iexact=word)
        qs = qs.filter(condition)
        filter_label = ", ".join(terms)
    else:
        filter_label = "tüm siparişler (izin verilen kapsam)"
    if years:
        qs = qs.filter(siparis_tarihi__year__in=years)
        filter_label += "; yillar=" + ", ".join(map(str, years))
    count = qs.count()
    total = qs.aggregate(adet=Sum("adet"))["adet"] or 0
    lines = [
        "DOGRULANMIS SQL ANALIZI (tum eslesen satirlar):",
        f"Filtre: {filter_label}",
        f"Kayit sayisi: {count}; toplam adet: {total}",
        "Musterilere gore ilk 25 (adet, kayit):",
    ]
    grouped = (qs.values("musteri__ad").annotate(adet=Sum("adet"), kayit=Count("id"))
               .order_by("-adet", "-kayit", "musteri__ad")[:MAX_GROUPS])
    for group in grouped:
        lines.append(f"- {group['musteri__ad'] or 'Musterisiz'}: {group['adet'] or 0} adet; {group['kayit']} kayit")
    if count:
        lines.append("Siparis yilina gore tum eslesen kayitlar:")
        annual = (qs.annotate(yil=ExtractYear("siparis_tarihi"))
                  .values("yil").annotate(adet=Sum("adet"), kayit=Count("id"))
                  .order_by("-yil")[:15])
        for item in annual:
            lines.append(f"- {item['yil'] or 'Tarihsiz'}: {item['adet'] or 0} adet; {item['kayit']} kayit")
    if count and has_access(user, "can_view_costs"):
        lines.append("Para birimine gore satis fiyati toplami (birim fiyat x adet):")
        from django.db.models import F, DecimalField, ExpressionWrapper
        amount = ExpressionWrapper(F("satis_fiyati") * F("adet"), output_field=DecimalField(max_digits=22, decimal_places=2))
        for item in qs.exclude(satis_fiyati__isnull=True).values("para_birimi").annotate(
                toplam=Sum(amount), kayit=Count("id")).order_by("para_birimi"):
            lines.append(f"- {item['para_birimi']}: {item['toplam']}; fiyatli kayit={item['kayit']}")
        lines.append("Para birimleri birbirine cevrilmedi. Fiyati eksik siparisler dahil edilmedi.")
    lines.append("Gruplar ilk 25 ile sinirlidir; toplam kayit ve adet sayisi SINIRSIZ eslesen kayittan hesaplandi.")
    return "\n".join(lines)
