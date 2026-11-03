"""Regression tests for BizimHesap product labels; no external API requests."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from django.test import SimpleTestCase
from .bizimhesap_payload import build_invoice_payload


class BizimHesapLineLabelTests(SimpleTestCase):
    def setUp(self):
        detail = SimpleNamespace(
            fatura_adresi="Test address", adres="", resmi_unvan="", vergi_dairesi="", vergi_numarasi=""
        )
        self.customer = SimpleNamespace(ad="Test customer", customer_detail=detail)
        self.invoice = SimpleNamespace(
            pk=80, customer=self.customer, customer_id=1,
            due_date=date(2026, 11, 2), invoice_date=date(2026, 11, 2),
            currency="TRY", status="DRAFT", official_number=""
        )
        self.mapping = SimpleNamespace(external_customer_id="TEST-CUSTOMER")

    def test_order_code_is_not_repeated_in_product_name(self):
        order = SimpleNamespace(
            urun_kodu="7182", renk="Pudra", beden="40",
            siparis_tipi="OZEL", musteri_referans="MDZI29162", para_birimi="TRY"
        )
        line = SimpleNamespace(
            order=order, price=Decimal("7750"), vat_rate=Decimal("10"), quantity=1
        )
        payload, problems = build_invoice_payload(self.invoice, [line], self.mapping, "TEST-FIRM")
        self.assertEqual(problems, [])
        item = payload["details"][0]
        self.assertEqual(item["productId"], "7182")
        self.assertEqual(item["productName"], "Pudra 40 ÖZEL MDZI29162")
        self.assertEqual(item["total"], "8525.00")

    def test_missing_color_or_size_blocks_export(self):
        order = SimpleNamespace(
            urun_kodu="7182", renk="", beden="44", siparis_tipi="OZEL",
            musteri_referans="MDZ29303", para_birimi="TRY"
        )
        line = SimpleNamespace(order=order, price=Decimal("8000"), vat_rate=Decimal("10"), quantity=1)
        payload, problems = build_invoice_payload(self.invoice, [line], self.mapping, "TEST-FIRM")
        self.assertIsNone(payload)
        self.assertTrue(any("renk ve beden" in problem for problem in problems))

    def test_manual_line_is_unchanged(self):
        line = SimpleNamespace(
            order=None, description="Accessories", quantity=Decimal("2"),
            unit_price=Decimal("100"), vat_rate=Decimal("10")
        )
        payload, problems = build_invoice_payload(self.invoice, [line], self.mapping, "TEST-FIRM")
        self.assertEqual(problems, [])
        self.assertEqual(payload["details"][0]["productId"], "Accessories")
        self.assertEqual(payload["details"][0]["productName"], "Accessories")
        self.assertEqual(payload["details"][0]["quantity"], "2")
