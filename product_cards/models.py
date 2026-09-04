from decimal import Decimal

from django.db import models
from core.models import UrunKod


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
