from types import SimpleNamespace
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import UrunKod, Order, OrderEvent, Musteri
from product_cards.models import Warehouse
from inventory.models import PreparationStock, PreparationUse
from inventory.views import _matching_preparations


class PreparationStockTests(TestCase):
    def setUp(self):
        self.product = UrunKod.objects.create(kod="TEST-PREP")
        self.warehouse = Warehouse.objects.create(kod="TESTPREP", ad="Test hazırlık")
        self.base = dict(product=self.product, warehouse=self.warehouse, color="Siyah",
                         stage="danteli_ayarlandi", initial_quantity=5,
                         remaining=5, prepared_by="test")

    def test_matching_does_not_mix_color_size_or_empty_stock(self):
        good = PreparationStock.objects.create(**self.base)
        sized = PreparationStock.objects.create(**self.base, size="38")
        PreparationStock.objects.create(**{**self.base, "color": "Beyaz"})
        PreparationStock.objects.create(**self.base, size="40")
        PreparationStock.objects.create(**{**self.base, "remaining": 0})
        order = SimpleNamespace(urun_kodu=self.product.kod, renk="Siyah", beden="38")
        self.assertEqual(set(_matching_preparations(order).values_list("pk", flat=True)), {good.pk, sized.pk})

    def test_preparation_does_not_create_order(self):
        before = Order.objects.count()
        PreparationStock.objects.create(**self.base)
        self.assertEqual(Order.objects.count(), before)
