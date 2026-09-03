from django.contrib import admin
from .models import Musteri, Order, Nakisci, Fasoncu, UrunKod

# Order için gelişmiş görünüm (filtre + liste alanları)
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'siparis_numarasi', 'musteri', 'urun_tipi', 'siparis_tarihi',
        'kesim_durum', 'dikim_durum', 'nakis_durumu',
        'susleme_durum', 'hazir_durum', 'sevkiyat_durum',
    )
    list_filter = (
        'siparis_tipi', 'urun_tipi', 'musteri', 'siparis_tarihi',
        'kesim_durum', 'dikim_durum', 'nakis_durumu',
        'susleme_durum', 'hazir_durum', 'sevkiyat_durum',
    )
    search_fields = ('siparis_numarasi', 'urun_kodu', 'musteri__ad')

# Diğer modeller aynen kalıyor
admin.site.register(Musteri)
admin.site.register(Nakisci)
admin.site.register(Fasoncu)


@admin.register(UrunKod)
class UrunKodAdmin(admin.ModelAdmin):
    list_display = ("kod", "urun_tipi", "aktif")
    list_filter = ("urun_tipi", "aktif")
    search_fields = ("kod",)
