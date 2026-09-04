from django import template

register = template.Library()

TRANSLATIONS = {
    "kesim_durum basladi": "Kesime Başlandı",
    "kesim_durum kismi_bitti": "Kısmi Kesim Yapıldı",
    "kesim_durum bitti": "Kesildi",
    "dikim_durum basladi": "Dikime Başlandı",
    "dikim_durum kismi_bitti": "Kısmi Dikim Yapıldı",
    "dikim_durum bitti": "Dikildi",
    "susleme_durum basladi": "Süslemeye Başlandı",
    "susleme_durum kismi_bitti": "Kısmi Süsleme Yapıldı",
    "susleme_durum bitti": "Süsleme Tamamlandı",
    "nakis_durumu verildi": "Nakışa Verildi",
    "nakis_durumu alindi": "Nakış Alındı",
    "dikim_fason_durumu verildi": "Fason Dikim Verildi",
    "dikim_fason_durumu alindi": "Fason Dikim Alındı",
    "susleme_fason_durumu verildi": "Fason Süsleme Verildi",
    "susleme_fason_durumu alindi": "Fason Süsleme Alındı",
    "sevkiyat_durum gonderildi": "Sevkiyata Gönderildi",
    "dikim_durum sıraya_alındı": "Dikime Alındı",
    "susleme_durum sıraya_alındı": "Süsleme Sırasına Alındı",
}


@register.filter
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def stage_translate(value):
    if not value:
        return "-"
    return TRANSLATIONS.get(value.strip(), value)


@register.simple_tag
def finance_result(order):
    """Sevkiyat snapshot ve sonraki finans hareketlerinden güncel sonucu döndürür."""
    from product_cards.finance_views import calculate_finance_result
    return calculate_finance_result(order)
