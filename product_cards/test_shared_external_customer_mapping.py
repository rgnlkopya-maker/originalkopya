"""Shared external customer mapping: two local branches can use one accounting customer."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Musteri
from product_cards.invoice_models import (
    BizimHesapCustomerMapping,
    ParasutCustomerMapping,
)


class SharedExternalCustomerMappingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_user(
            username="shared_mapping_manager", password="sample-pass", is_superuser=True
        )
        cls.saraclar = Musteri.objects.create(ad="SITARE SARACLAR", aktif=True)
        cls.yokus = Musteri.objects.create(ad="SITARE YOKUS", aktif=True)

    def test_multiple_branches_share_bizimhesap_customer(self):
        self.client.force_login(self.manager)
        for customer in (self.saraclar, self.yokus):
            response = self.client.post(
                reverse("invoice_customer_mapping_save", args=[customer.pk]),
                {"external_customer_id": "SITARE-CARI"},
            )
            self.assertEqual(response.status_code, 302)
        self.assertEqual(
            BizimHesapCustomerMapping.objects.filter(
                external_customer_id="SITARE-CARI"
            ).count(), 2
        )

    def test_multiple_branches_share_parasut_contact(self):
        self.client.force_login(self.manager)
        for customer in (self.saraclar, self.yokus):
            response = self.client.post(
                reverse("invoice_parasut_mapping_save", args=[customer.pk]),
                {"external_contact_id": "123456789"},
            )
            self.assertEqual(response.status_code, 302)
        self.assertEqual(
            ParasutCustomerMapping.objects.filter(
                external_contact_id="123456789"
            ).count(), 2
        )
