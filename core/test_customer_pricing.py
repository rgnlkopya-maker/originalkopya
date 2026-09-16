from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import CustomerPricingRule, Musteri, Order, Renk, UrunKod


class CustomerPricingRuleTests(TestCase):
    def setUp(self):
        self.customer = Musteri.objects.create(ad="MODAZEHRADA")
        self.rule = CustomerPricingRule.objects.create(customer=self.customer)

    def test_hip_measurement_and_price_groups(self):
        cases = [
            ("97", 38, "250"),
            ("102", 38, "250"),
            ("103", 40, "250"),
            ("107", 42, "250"),
            ("111", 44, "500"),
            ("123", 50, "750"),
            ("135", 56, "1000"),
        ]
        for hip, expected_size, expected_adjustment in cases:
            with self.subTest(hip=hip):
                size, adjustment, final_price = self.rule.calculate(hip, Decimal("10000"))
                self.assertEqual(size, expected_size)
                self.assertEqual(adjustment, Decimal(expected_adjustment))
                self.assertEqual(final_price, Decimal("10000") + Decimal(expected_adjustment))


class ModazehraOrderCreateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("pricing-manager", password="test-password")
        manager_group, _ = Group.objects.get_or_create(name="patron")
        self.user.groups.add(manager_group)
        self.client.force_login(self.user)
        self.customer = Musteri.objects.create(ad="MODAZEHRADA")
        CustomerPricingRule.objects.create(customer=self.customer)
        Renk.objects.create(ad="Siyah")
        UrunKod.objects.create(kod="MODA-X", urun_tipi="DIGER")

    def test_each_measurement_creates_orders_with_calculated_size_and_price(self):
        response = self.client.post(
            reverse("order_multi_create"),
            {
                "siparis_tipi": "SERI",
                "musteri": str(self.customer.pk),
                "urun_kodu": "MODA-X",
                "urun_tipi": "DIGER",
                "renk_row_0": "Siyah",
                "basen_row_0": "113",
                "adet_row_0": "2",
                "musteri_ref_row_0": "MZ-1",
                "satis_fiyati": "10000",
                "para_birimi": "TRY",
            },
        )

        self.assertRedirects(response, reverse("order_list"))
        orders = list(Order.objects.filter(musteri=self.customer).order_by("id"))
        self.assertEqual(len(orders), 2)
        for order in orders:
            self.assertEqual(order.beden, "44")
            self.assertEqual(order.hip_measurement, Decimal("113"))
            self.assertEqual(order.customer_base_price, Decimal("10000"))
            self.assertEqual(order.customer_price_adjustment, Decimal("500"))
            self.assertEqual(order.satis_fiyati, Decimal("10500"))

    def test_missing_measurement_does_not_create_partial_orders(self):
        response = self.client.post(
            reverse("order_multi_create"),
            {
                "siparis_tipi": "SERI",
                "musteri": str(self.customer.pk),
                "urun_kodu": "MODA-X",
                "urun_tipi": "DIGER",
                "renk_row_0": "Siyah",
                "adet_row_0": "1",
                "satis_fiyati": "10000",
            },
        )

        self.assertRedirects(response, reverse("order_multi_create"))
        self.assertFalse(Order.objects.exists())
