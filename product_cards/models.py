from decimal import Decimal

from django.db import models
from core.models import UrunKod


class ProductCard(models.Model):
    urun = models.OneToOneField(UrunKod, on_delete=models.CASCADE, related_name="product_card")
    aciklama = models.TextField(blank=True, default="")
    image_url = models.URLField(blank=True, default="")
    iscilik_maliyeti = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    genel_gider = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    diger_maliyet = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def malzeme_maliyeti(self):
        total = Decimal("0")
        for usage in self.materials.select_related("material").all():
            total += usage.miktar * usage.material.birim_maliyet
        return total

    @property
    def toplam_maliyet(self):
        return self.malzeme_maliyeti + self.iscilik_maliyeti + self.genel_gider + self.diger_maliyet

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
    birim_maliyet = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    image_url = models.URLField(blank=True, default="")
    aktif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
        return self.miktar * self.material.birim_maliyet

    def __str__(self):
        return f"{self.product_card.urun.kod} - {self.material.ad}: {self.miktar}"
