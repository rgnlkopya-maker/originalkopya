"""Regression tests for BizimHesap product labels; no external API requests."""
from datetime import date
from decimal import Decimal
from hashlib import sha256
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
        self.assertEqual(item["productId"], "MOLI-7182-" + sha256("7182 Pudra 40 ÖZEL MDZI29162".encode("utf-8")).hexdigest()[:12])
        self.assertEqual(item["productName"], "7182 Pudra 40 ÖZEL MDZI29162")
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

    def test_same_model_with_different_size_has_distinct_product_identity(self):
        def make_line(size):
            order = SimpleNamespace(
                urun_kodu="7176", renk="Pudra", beden=size,
                siparis_tipi="OZEL", musteri_referans="MDZ129477", para_birimi="TRY"
            )
            return SimpleNamespace(order=order, price=Decimal("20000"),
                                   vat_rate=Decimal("10"), quantity=1)
        payload, problems = build_invoice_payload(
            self.invoice, [make_line("40"), make_line("42")], self.mapping, "TEST-FIRM"
        )
        self.assertEqual(problems, [])
        first, second = payload["details"]
        self.assertNotEqual(first["productId"], second["productId"])
        self.assertEqual(first["productName"], "7176 Pudra 40 ÖZEL MDZ129477")
        self.assertEqual(second["productName"], "7176 Pudra 42 ÖZEL MDZ129477")
        self.assertEqual(payload["amounts"]["total"], "44000.00")

    def test_same_exact_label_reuses_identity(self):
        order = SimpleNamespace(
            urun_kodu="7176", renk="Pudra", beden="42", siparis_tipi="OZEL",
            musteri_referans="MDZ129477", para_birimi="TRY"
        )
        line = SimpleNamespace(order=order, price=Decimal("10000"), vat_rate=Decimal("10"), quantity=1)
        first, problems1 = build_invoice_payload(self.invoice, [line], self.mapping, "TEST-FIRM")
        second, problems2 = build_invoice_payload(self.invoice, [line], self.mapping, "TEST-FIRM")
        self.assertEqual(problems1, [])
        self.assertEqual(problems2, [])
        self.assertEqual(first["details"][0]["productId"], second["details"][0]["productId"])

    def test_distinct_references_do_not_reuse_stale_catalog_label(self):
        def make_line(reference):
            order = SimpleNamespace(
                urun_kodu="7176", renk="Pudra", beden="42",
                siparis_tipi="OZEL", musteri_referans=reference, para_birimi="TRY"
            )
            return SimpleNamespace(order=order, price=Decimal("10000"),
                                   vat_rate=Decimal("10"), quantity=1)
        payload, problems = build_invoice_payload(
            self.invoice, [make_line("MDZ129477"), make_line("MDZ129478")],
            self.mapping, "TEST-FIRM"
        )
        self.assertEqual(problems, [])
        self.assertNotEqual(payload["details"][0]["productId"], payload["details"][1]["productId"])
        self.assertEqual(payload["details"][1]["productName"], "7176 Pudra 42 ÖZEL MDZ129478")
