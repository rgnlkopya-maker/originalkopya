from django.conf import settings
from django.db import models

from core.models import UrunKod
from product_cards.models import Warehouse


class ProductWarehouseStock(models.Model):
    product = models.ForeignKey(UrunKod, on_delete=models.PROTECT, related_name="warehouse_stocks")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="product_stocks")
    quantity = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "warehouse"], name="unique_product_warehouse_stock")]
        ordering = ["product__kod"]


class ProductStockMovement(models.Model):
    TYPE_CHOICES = [
        ("GIRIS", "Stok Girişi"),
        ("CIKIS", "Stok Çıkışı"),
        ("IADE", "İade Girişi"),
        ("DUZELTME_ARTI", "Sayım Düzeltmesi +"),
        ("DUZELTME_EKSI", "Sayım Düzeltmesi -"),
    ]
    product = models.ForeignKey(UrunKod, on_delete=models.PROTECT, related_name="warehouse_movements")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="product_movements")
    movement_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    quantity = models.PositiveIntegerField()
    previous_stock = models.PositiveIntegerField(default=0)
    resulting_stock = models.PositiveIntegerField(default=0)
    note = models.CharField(max_length=255, blank=True, default="")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


LACE_STAGES = [
    ("danteli_ayarlandi", "Danteli Ayarlandı"),
    ("etek_danteli_ayarlandi", "Etek Danteli Ayarlandı"),
    ("beden_danteli_ayarlandi", "Beden Danteli Ayarlandı"),
    ("takim_olarak_danteli_ayarlandi", "Takım Olarak Danteli Ayarlandı"),
]


class PreparationStock(models.Model):
    product = models.ForeignKey(UrunKod, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    color = models.CharField(max_length=100)
    size = models.CharField(max_length=20, blank=True, default="")
    stage = models.CharField(max_length=40, choices=LACE_STAGES)
    initial_quantity = models.PositiveIntegerField()
    remaining = models.PositiveIntegerField()
    note = models.CharField(max_length=255, blank=True, default="")
    prepared_by = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class PreparationUse(models.Model):
    stock = models.ForeignKey(PreparationStock, on_delete=models.PROTECT, related_name="uses")
    order = models.ForeignKey("core.Order", on_delete=models.PROTECT)
    event = models.ForeignKey("core.OrderEvent", on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField(default=1)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
