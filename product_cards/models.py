from decimal import Decimal

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import Order, OrderEvent, ProductCost, UrunKod


CURRENCY_CHOICES = [
    ("TRY", "TL"),
    ("USD", "USD"),
]


class ExchangeRate(models.Model):
    rate_date = models.DateField(unique=True)
    usd_try = models.DecimalField(max_digits=12, decimal_places=6)
    source_date = models.CharField(max_length=20, blank=True, default="")
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-rate_date"]

    @classmethod
    def latest_usd_try(cls):
        obj = cls.objects.order_by("-rate_date", "-fetched_at").first()
        return obj.usd_try if obj else Decimal("1")

    def __str__(self):
        return f"{self.rate_date} USD/TRY {self.usd_try}"


def to_try(amount, currency):
    amount = amount or Decimal("0")
    if currency == "USD":
        return amount * ExchangeRate.latest_usd_try()
    return amount


def amount_to_try(amount, currency, usd_try):
    """Snapshot hesabinda verilen sabit kuru kullanarak TL karsiligini dondurur."""
    if amount is None:
        return None
    amount = Decimal(amount)
    if currency == "USD":
        return amount * usd_try if usd_try else None
    return amount


class OrderFinancialSnapshot(models.Model):
    """Siparis olusturuldugu andaki finansal fotografin degismeyen kaydi."""

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="financial_snapshot",
    )
    usd_try = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    satis_fiyati = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    satis_para_birimi = models.CharField(max_length=3, default="TRY")
    satis_tl = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    maliyet_tl = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    beklenen_kar_tl = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    beklenen_kar_orani = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order.siparis_numarasi} - siparis gunu finans"


class ShipmentFinancialSnapshot(models.Model):
    """Urun sevk edildigi andaki gercek finansal sonucu degismeden saklar."""

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="shipment_financial_snapshot",
    )
    usd_try = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    satis_fiyati = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    satis_para_birimi = models.CharField(max_length=3, default="TRY")
    satis_tl = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    urun_maliyeti_tl = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    sevkiyat_ekstra_maliyet_tl = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    toplam_maliyet_tl = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    gerceklesen_kar_tl = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    gerceklesen_kar_orani = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    notlar = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order.siparis_numarasi} - sevkiyat gunu finans"


@receiver(post_save, sender=Order)
def create_order_financial_snapshot(sender, instance, created, **kwargs):
    """Yeni sipariste o anki kur, satis ve maliyeti sabitler; sonraki kur degisimlerinden etkilenmez."""
    if not created:
        return

    rate_obj = ExchangeRate.objects.order_by("-rate_date", "-fetched_at").first()
    usd_try = rate_obj.usd_try if rate_obj else None

    satis = instance.satis_fiyati
    satis_currency = instance.para_birimi or "TRY"
    satis_tl = None
    if satis is not None:
        satis = Decimal(satis)
        if satis_currency == "TRY":
            satis_tl = satis
        elif satis_currency == "USD" and usd_try:
            satis_tl = satis * usd_try

    # Sipariste elle override varsa onu; yoksa siparise cekilen ProductCost degerini kullan.
    cost_available = instance.maliyet_override is not None
    effective_cost = Decimal(instance.maliyet_override) if instance.maliyet_override is not None else None

    if effective_cost is None and instance.maliyet_uygulanan is not None:
        pc_exists = ProductCost.objects.filter(
            urun_kodu__iexact=instance.urun_kodu or "",
            is_active=True,
        ).exists()
        if pc_exists or Decimal(instance.maliyet_uygulanan or 0) != 0:
            effective_cost = Decimal(instance.maliyet_uygulanan or 0)
            cost_available = True

    maliyet_tl = None
    if cost_available and effective_cost is not None:
        ekstra = Decimal(instance.ekstra_maliyet or 0)
        total_cost = effective_cost + ekstra
        cost_currency = instance.maliyet_para_birimi or "TRY"
        if cost_currency == "TRY":
            maliyet_tl = total_cost
        elif cost_currency == "USD" and usd_try:
            maliyet_tl = total_cost * usd_try

    kar_tl = None
    kar_orani = None
    if satis_tl is not None and maliyet_tl is not None:
        kar_tl = satis_tl - maliyet_tl
        if satis_tl != 0:
            kar_orani = (kar_tl / satis_tl) * Decimal("100")

    OrderFinancialSnapshot.objects.get_or_create(
        order=instance,
        defaults={
            "usd_try": usd_try,
            "satis_fiyati": satis,
            "satis_para_birimi": satis_currency,
            "satis_tl": satis_tl.quantize(Decimal("0.01")) if satis_tl is not None else None,
            "maliyet_tl": maliyet_tl.quantize(Decimal("0.01")) if maliyet_tl is not None else None,
            "beklenen_kar_tl": kar_tl.quantize(Decimal("0.01")) if kar_tl is not None else None,
            "beklenen_kar_orani": kar_orani.quantize(Decimal("0.01")) if kar_orani is not None else None,
        },
    )


@receiver(post_save, sender=OrderEvent)
def create_shipment_financial_snapshot(sender, instance, created, **kwargs):
    """Sevkedildi eventi ilk kez olustugunda sevkiyat gunu finans sonucunu dondurur."""
    if not created or instance.stage != "sevkiyat_durum" or instance.value != "gonderildi":
        return

    order = instance.order

    # Ayni siparis tekrar sevkedildi olarak isaretlense bile ilk gercek sevkiyat kaydi degismez.
    if ShipmentFinancialSnapshot.objects.filter(order=order).exists():
        return

    rate_obj = ExchangeRate.objects.order_by("-rate_date", "-fetched_at").first()
    usd_try = rate_obj.usd_try if rate_obj else None

    # Nihai satis fiyati: sevkiyat aninda Order uzerinde hangi fiyat varsa odur.
    satis = Decimal(order.satis_fiyati) if order.satis_fiyati is not None else None
    satis_currency = order.para_birimi or "TRY"
    satis_tl = amount_to_try(satis, satis_currency, usd_try)

    # Sevkiyat gunu urun maliyeti: siparis gunundeki eski maliyet yerine guncel ProductCost kullanilir.
    # Elle maliyet override girilmisse bu bilincli tercih oldugu icin onceliklidir.
    urun_maliyeti = None
    cost_currency = "TRY"
    if order.maliyet_override is not None:
        urun_maliyeti = Decimal(order.maliyet_override)
        cost_currency = order.maliyet_para_birimi or "TRY"
    else:
        product_cost = ProductCost.objects.filter(
            urun_kodu__iexact=order.urun_kodu or "",
            is_active=True,
        ).first()
        if product_cost:
            urun_maliyeti = Decimal(product_cost.maliyet)
            cost_currency = product_cost.para_birimi or "TRY"
        elif order.maliyet_uygulanan is not None:
            # Eski/eksik urun kartlarinda finans kaydi tamamen bos kalmasin.
            urun_maliyeti = Decimal(order.maliyet_uygulanan)
            cost_currency = order.maliyet_para_birimi or "TRY"

    urun_maliyeti_tl = amount_to_try(urun_maliyeti, cost_currency, usd_try)

    # Musterinin sonradan istedigi ek isler icin Order.ekstra_maliyet sevkiyat aninda dahil edilir.
    ekstra = Decimal(order.ekstra_maliyet or 0)
    ekstra_tl = amount_to_try(ekstra, cost_currency, usd_try) or Decimal("0")

    toplam_maliyet_tl = None
    if urun_maliyeti_tl is not None:
        toplam_maliyet_tl = urun_maliyeti_tl + ekstra_tl

    kar_tl = None
    kar_orani = None
    if satis_tl is not None and toplam_maliyet_tl is not None:
        kar_tl = satis_tl - toplam_maliyet_tl
        if satis_tl != 0:
            kar_orani = (kar_tl / satis_tl) * Decimal("100")

    ShipmentFinancialSnapshot.objects.create(
        order=order,
        usd_try=usd_try,
        satis_fiyati=satis,
        satis_para_birimi=satis_currency,
        satis_tl=satis_tl.quantize(Decimal("0.01")) if satis_tl is not None else None,
        urun_maliyeti_tl=urun_maliyeti_tl.quantize(Decimal("0.01")) if urun_maliyeti_tl is not None else None,
        sevkiyat_ekstra_maliyet_tl=ekstra_tl.quantize(Decimal("0.01")),
        toplam_maliyet_tl=toplam_maliyet_tl.quantize(Decimal("0.01")) if toplam_maliyet_tl is not None else None,
        gerceklesen_kar_tl=kar_tl.quantize(Decimal("0.01")) if kar_tl is not None else None,
        gerceklesen_kar_orani=kar_orani.quantize(Decimal("0.01")) if kar_orani is not None else None,
    )


class ProductCard(models.Model):
    urun = models.OneToOneField(UrunKod, on_delete=models.CASCADE, related_name="product_card")
    aciklama = models.TextField(blank=True, default="")
    image_url = models.URLField(blank=True, default="")

    finansman_maliyeti = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    finansman_para_birimi = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="TRY")
    nakis_maliyeti = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    nakis_para_birimi = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="TRY")
    genel_gider = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    genel_gider_para_birimi = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="TRY")
    iscilik_maliyeti = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    iscilik_para_birimi = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="TRY")
    paketleme_maliyeti = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    paketleme_para_birimi = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="TRY")

    # Eski kayitlarla uyumluluk icin tutuluyor; yeni maliyet ekraninda kullanilmiyor.
    diger_maliyet = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    diger_maliyet_para_birimi = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="TRY")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def malzeme_maliyeti(self):
        total = Decimal("0")
        for usage in self.materials.select_related("material").all():
            total += usage.satir_maliyeti
        return total

    @property
    def finansman_maliyeti_tl(self):
        return to_try(self.finansman_maliyeti, self.finansman_para_birimi)

    @property
    def nakis_maliyeti_tl(self):
        return to_try(self.nakis_maliyeti, self.nakis_para_birimi)

    @property
    def genel_gider_tl(self):
        return to_try(self.genel_gider, self.genel_gider_para_birimi)

    @property
    def iscilik_maliyeti_tl(self):
        return to_try(self.iscilik_maliyeti, self.iscilik_para_birimi)

    @property
    def paketleme_maliyeti_tl(self):
        return to_try(self.paketleme_maliyeti, self.paketleme_para_birimi)

    @property
    def toplam_maliyet(self):
        return (
            self.malzeme_maliyeti
            + self.finansman_maliyeti_tl
            + self.nakis_maliyeti_tl
            + self.genel_gider_tl
            + self.iscilik_maliyeti_tl
            + self.paketleme_maliyeti_tl
        )

    def __str__(self):
        return f"Ürün Kartı - {self.urun.kod}"


class Material(models.Model):
    UNIT_CHOICES = [
        ("M", "Metre"),
        ("ADET", "Adet"),
        ("KG", "Kilogram"),
        ("GR", "Gram"),
    ]

    kod = models.CharField(max_length=80, unique=True)
    ad = models.CharField(max_length=160)
    birim = models.CharField(max_length=10, choices=UNIT_CHOICES, default="M")
    stok_miktari = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    birim_maliyet = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    birim_maliyet_para_birimi = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="TRY")
    image_url = models.URLField(blank=True, default="")
    aktif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def birim_maliyet_tl(self):
        return to_try(self.birim_maliyet, self.birim_maliyet_para_birimi)

    def __str__(self):
        return f"{self.kod} - {self.ad}"


class ProductMaterial(models.Model):
    product_card = models.ForeignKey(ProductCard, on_delete=models.CASCADE, related_name="materials")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="product_usages")
    miktar = models.DecimalField(max_digits=12, decimal_places=3)
    notlar = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product_card", "material"], name="unique_product_material")
        ]
        ordering = ["material__ad"]

    @property
    def satir_maliyeti(self):
        return self.miktar * self.material.birim_maliyet_tl

    def __str__(self):
        return f"{self.product_card.urun.kod} - {self.material.ad}: {self.miktar}"
