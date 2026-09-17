import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import CustomerPricingRule, Musteri, Order, OrderEvent, ProductCost, UrunKod
from .finance_views import calculate_finance_result
from .models import ExchangeRate, Material, OrderFinancialSnapshot, PriceListSettings, ProductCard, ProductMaterial, ShipmentFinancialSnapshot, ShowroomDraft, ShowroomDraftItem


class MaterialCostEditTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("material-manager", password="test")
        patron, _ = Group.objects.get_or_create(name="patron")
        self.user.groups.add(patron)
        self.client.force_login(self.user)
        ExchangeRate.objects.create(rate_date=timezone.localdate(), usd_try=Decimal("40.000000"))
        product = UrunKod.objects.create(kod="MAT-TEST")
        self.card, _ = ProductCard.objects.get_or_create(urun=product)
        self.material = Material.objects.create(
            kod="KUMAS-TEST",
            ad="Test Kumaşı",
            kategori="KUMAS",
            kullanim_asamasi="KESIM",
            birim="M",
            birim_maliyet=Decimal("10.0000"),
            birim_maliyet_para_birimi="TRY",
        )
        ProductMaterial.objects.create(
            product_card=self.card,
            material=self.material,
            miktar=Decimal("2.000"),
            kullanim_asamasi="KESIM",
        )
        ProductCost.objects.create(
            urun_kodu=product.kod,
            maliyet=Decimal("20.00"),
            para_birimi="TRY",
            is_active=True,
        )

    def _create_order(self):
        with patch("core.signals_qr.ensure_order_qr"):
            return Order.objects.create(
                siparis_tipi="SERI",
                urun_kodu="MAT-TEST",
                satis_fiyati=Decimal("500.00"),
                para_birimi="TRY",
                maliyet_uygulanan=Decimal("20.00"),
                maliyet_para_birimi="TRY",
            )

    def test_material_edit_updates_cost_currency_and_approved_product_cost(self):
        open_order = self._create_order()
        shipped_order = self._create_order()
        OrderEvent.objects.create(
            order=shipped_order,
            user="test",
            stage="sevkiyat_durum",
            value="gonderildi",
        )

        response = self.client.post(
            reverse("material_list"),
            {
                "action": "update_info",
                "id": str(self.material.pk),
                "kategori": "KUMAS",
                "kullanim_asamasi": "KESIM",
                "tedarikci": "",
                "kritik_stok": "0",
                "birim_maliyet": "3.0000",
                "birim_maliyet_para_birimi": "USD",
                "son_alis_tarihi": "",
                "aciklama": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.material.refresh_from_db()
        product_cost = ProductCost.objects.get(urun_kodu="MAT-TEST", is_active=True)

        self.assertEqual(self.material.birim_maliyet, Decimal("3.0000"))
        self.assertEqual(self.material.birim_maliyet_para_birimi, "USD")
        self.assertEqual(product_cost.maliyet, Decimal("240.00"))
        self.assertEqual(product_cost.para_birimi, "TRY")

        open_order.refresh_from_db()
        open_snapshot = OrderFinancialSnapshot.objects.get(order=open_order)
        self.assertEqual(open_order.maliyet_uygulanan, Decimal("240.00"))
        self.assertEqual(open_snapshot.maliyet_tl, Decimal("240.00"))
        self.assertEqual(open_snapshot.beklenen_kar_tl, Decimal("260.00"))
        self.assertEqual(open_snapshot.beklenen_kar_orani, Decimal("52.00"))

        shipped_order.refresh_from_db()
        shipped_order_snapshot = OrderFinancialSnapshot.objects.get(order=shipped_order)
        shipment_snapshot = ShipmentFinancialSnapshot.objects.get(order=shipped_order)
        self.assertEqual(shipped_order.maliyet_uygulanan, Decimal("20.00"))
        self.assertEqual(shipped_order_snapshot.maliyet_tl, Decimal("20.00"))
        self.assertEqual(shipment_snapshot.urun_maliyeti_tl, Decimal("20.00"))
        self.assertEqual(shipment_snapshot.toplam_maliyet_tl, Decimal("20.00"))


class FinanceSnapshotRegressionTests(TestCase):
    def setUp(self):
        ExchangeRate.objects.create(rate_date="2026-09-05", usd_try=Decimal("48.319500"))
        ProductCost.objects.create(
            urun_kodu="7165",
            maliyet=Decimal("9253.52"),
            para_birimi="TRY",
            is_active=True,
        )

    def _create_order(self, **kwargs):
        defaults = {
            "siparis_tipi": "SERI",
            "urun_kodu": "7165",
            "satis_fiyati": Decimal("13000.00"),
            "para_birimi": "TRY",
            "maliyet_para_birimi": "TRY",
        }
        defaults.update(kwargs)
        with patch("core.signals_qr.ensure_order_qr"):
            return Order.objects.create(**defaults)

    def test_order_snapshot_uses_active_product_cost_when_order_cost_is_zero(self):
        order = self._create_order(maliyet_uygulanan=Decimal("0"))
        order.refresh_from_db()
        snapshot = OrderFinancialSnapshot.objects.get(order=order)

        self.assertEqual(order.maliyet_uygulanan, Decimal("9253.52"))
        self.assertEqual(snapshot.satis_tl, Decimal("13000.00"))
        self.assertEqual(snapshot.maliyet_tl, Decimal("9253.52"))
        self.assertEqual(snapshot.beklenen_kar_tl, Decimal("3746.48"))
        self.assertEqual(snapshot.beklenen_kar_orani, Decimal("28.82"))

    def test_incomplete_snapshot_repairs_when_sale_price_is_saved_after_creation(self):
        order = self._create_order(satis_fiyati=Decimal("0"), maliyet_uygulanan=Decimal("0"))
        snapshot = OrderFinancialSnapshot.objects.get(order=order)
        self.assertEqual(snapshot.satis_tl, Decimal("0.00"))

        order.satis_fiyati = Decimal("13000.00")
        order.save(update_fields=["satis_fiyati"])
        snapshot.refresh_from_db()

        self.assertEqual(snapshot.satis_tl, Decimal("13000.00"))
        self.assertEqual(snapshot.maliyet_tl, Decimal("9253.52"))
        self.assertEqual(snapshot.beklenen_kar_tl, Decimal("3746.48"))
        self.assertEqual(snapshot.beklenen_kar_orani, Decimal("28.82"))

    def test_complete_snapshot_updates_when_sale_price_changes(self):
        order = self._create_order(maliyet_uygulanan=Decimal("0"))
        snapshot = OrderFinancialSnapshot.objects.get(order=order)

        order.satis_fiyati = Decimal("14000.00")
        order.save(update_fields=["satis_fiyati"])
        snapshot.refresh_from_db()

        self.assertEqual(snapshot.satis_fiyati, Decimal("14000.00"))
        self.assertEqual(snapshot.satis_tl, Decimal("14000.00"))
        self.assertEqual(snapshot.maliyet_tl, Decimal("9253.52"))
        self.assertEqual(snapshot.beklenen_kar_tl, Decimal("4746.48"))
        self.assertEqual(snapshot.beklenen_kar_orani, Decimal("33.90"))

    def test_sale_price_change_after_shipment_keeps_snapshot_cost_frozen(self):
        order = self._create_order(maliyet_uygulanan=Decimal("0"))
        OrderEvent.objects.create(
            order=order,
            user="test",
            stage="sevkiyat_durum",
            value="gonderildi",
        )
        snapshot = OrderFinancialSnapshot.objects.get(order=order)

        ProductCost.objects.filter(urun_kodu="7165", is_active=True).update(
            maliyet=Decimal("10000.00")
        )
        order.satis_fiyati = Decimal("14000.00")
        order.save(update_fields=["satis_fiyati"])
        snapshot.refresh_from_db()

        self.assertEqual(snapshot.satis_fiyati, Decimal("14000.00"))
        self.assertEqual(snapshot.satis_tl, Decimal("14000.00"))
        self.assertEqual(snapshot.maliyet_tl, Decimal("9253.52"))
        self.assertEqual(snapshot.beklenen_kar_tl, Decimal("4746.48"))
        self.assertEqual(snapshot.beklenen_kar_orani, Decimal("33.90"))

    def test_shipment_snapshot_uses_current_sale_and_active_product_cost(self):
        order = self._create_order(maliyet_uygulanan=Decimal("0"))
        OrderEvent.objects.create(
            order=order,
            user="test",
            stage="sevkiyat_durum",
            value="gonderildi",
        )

        snapshot = ShipmentFinancialSnapshot.objects.get(order=order)
        self.assertEqual(snapshot.satis_tl, Decimal("13000.00"))
        self.assertEqual(snapshot.urun_maliyeti_tl, Decimal("9253.52"))
        self.assertEqual(snapshot.toplam_maliyet_tl, Decimal("9253.52"))
        self.assertEqual(snapshot.gerceklesen_kar_tl, Decimal("3746.48"))
        self.assertEqual(snapshot.gerceklesen_kar_orani, Decimal("28.82"))

    def test_shipment_finance_discount_and_extra_cost_are_calculated_without_changing_shipping_status(self):
        order = self._create_order(maliyet_uygulanan=Decimal("0"))
        OrderEvent.objects.create(order=order, user="test", stage="sevkiyat_durum", value="gonderildi")
        OrderEvent.objects.create(
            order=order,
            user="manager",
            stage="finans_hareketi",
            value="INDIRIM",
            event_type="order_update",
            new_value=json.dumps({"tl_amount": "1000.00"}),
        )
        OrderEvent.objects.create(
            order=order,
            user="manager",
            stage="finans_hareketi",
            value="EK_MALIYET",
            event_type="order_update",
            new_value=json.dumps({"tl_amount": "500.00"}),
        )

        result = calculate_finance_result(order)
        self.assertEqual(result["status"], "SEVKEDILDI")
        self.assertTrue(result["is_final"])
        self.assertEqual(result["satis_tl"], Decimal("12000.00"))
        self.assertEqual(result["maliyet_tl"], Decimal("9753.52"))
        self.assertEqual(result["kar_tl"], Decimal("2246.48"))
        self.assertEqual(result["kar_orani"], Decimal("18.72"))
        self.assertEqual(len(result["movements"]), 2)

    def test_return_then_reship_restores_sale_and_keeps_prior_discount(self):
        order = self._create_order(maliyet_uygulanan=Decimal("0"))
        OrderEvent.objects.create(order=order, user="test", stage="sevkiyat_durum", value="gonderildi")
        OrderEvent.objects.create(
            order=order,
            user="manager",
            stage="finans_hareketi",
            value="INDIRIM",
            event_type="order_update",
            new_value=json.dumps({"tl_amount": "1000.00"}),
        )
        OrderEvent.objects.create(order=order, user="test", stage="sevkiyat_durum", value="iade_geldi")

        returned = calculate_finance_result(order)
        self.assertEqual(returned["status"], "IADE")
        self.assertEqual(returned["satis_tl"], Decimal("0.00"))

        OrderEvent.objects.create(order=order, user="test", stage="sevkiyat_durum", value="gonderildi")
        resent = calculate_finance_result(order)
        self.assertEqual(resent["status"], "SEVKEDILDI")
        self.assertEqual(resent["satis_tl"], Decimal("12000.00"))
        self.assertEqual(resent["kar_tl"], Decimal("2746.48"))


class MultiOrderFinancePostTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("finance-manager", password="test")
        patron, _ = Group.objects.get_or_create(name="patron")
        self.user.groups.add(patron)
        self.client.force_login(self.user)
        self.customer = Musteri.objects.create(ad="Finans Test Müşteri")
        ExchangeRate.objects.create(rate_date="2026-09-05", usd_try=Decimal("48.319500"))
        ProductCost.objects.create(
            urun_kodu="7165",
            maliyet=Decimal("9253.52"),
            para_birimi="TRY",
            is_active=True,
        )

    @patch("core.signals_qr.ensure_order_qr")
    def test_multi_order_post_preserves_sale_price_and_builds_profit_snapshot(self, _qr):
        response = self.client.post(
            "/orders/multi-create/",
            {
                "siparis_tipi": "SERI",
                "musteri": str(self.customer.pk),
                "urun_kodu": "7165",
                "urun_tipi": "BALIK",
                "renk_row_0": "TAŞ",
                "beden_row_0[]": ["38"],
                "adet_row_0": "1",
                "musteri_ref_row_0": "",
                "teslim_tarihi": "",
                "aciklama": "",
                "satis_fiyati": "13000.00",
                "para_birimi": "TRY",
                "maliyet_uygulanan": "",
                "maliyet_para_birimi": "TRY",
            },
        )

        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(urun_kodu="7165")
        order.refresh_from_db()
        snapshot = OrderFinancialSnapshot.objects.get(order=order)

        self.assertEqual(order.satis_fiyati, Decimal("13000.00"))
        self.assertEqual(order.maliyet_uygulanan, Decimal("9253.52"))
        self.assertEqual(snapshot.satis_tl, Decimal("13000.00"))
        self.assertEqual(snapshot.maliyet_tl, Decimal("9253.52"))
        self.assertEqual(snapshot.beklenen_kar_tl, Decimal("3746.48"))

class PriceListTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "price-manager", password="test-password"
        )
        patron, _ = Group.objects.get_or_create(name="patron")
        self.manager.groups.add(patron)
        self.client.force_login(self.manager)
        self.settings = PriceListSettings.objects.create(
            pk=1,
            profit_rate=Decimal("20"),
            discount_rate=Decimal("5"),
            monthly_term_rate=Decimal("2"),
            usd_try=Decimal("40"),
            eur_try=Decimal("45"),
            rate_source="TCMB",
            rate_checked_at=timezone.now(),
        )

    def test_new_product_card_appears_in_matching_group(self):
        product = UrunKod.objects.create(kod="PRICE-FISH", urun_tipi="BALIK")
        ProductCard.objects.get_or_create(urun=product)

        response = self.client.get(reverse("price_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PRICE-FISH")

    def test_all_product_cards_appear_without_group_filter(self):
        product = UrunKod.objects.create(kod="PRICE-HELEN", urun_tipi="HELEN")
        ProductCard.objects.get_or_create(urun=product)

        response = self.client.get(reverse("price_list"))

        self.assertContains(response, "PRICE-HELEN")
        self.assertNotContains(response, "Güncel Maliyet")

    def test_product_codes_are_sorted_alphabetically(self):
        for code in ("ZZ-PRICE", "AA-PRICE"):
            product = UrunKod.objects.create(kod=code, urun_tipi="DIGER")
            ProductCard.objects.get_or_create(urun=product)

        response = self.client.get(reverse("price_list"))
        content = response.content.decode()

        self.assertLess(content.index("AA-PRICE"), content.index("ZZ-PRICE"))

    def test_settings_are_saved_automatically_by_endpoint(self):
        response = self.client.post(reverse("save_price_list_settings"), {
            "profit_rate": "25",
            "discount_rate": "7.5",
            "monthly_term_rate": "2.5",
            "usd_try": "41",
            "eur_try": "46",
            "changed_field": "profit_rate",
        })

        self.assertEqual(response.status_code, 200)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.profit_rate, Decimal("25"))
        self.assertEqual(self.settings.discount_rate, Decimal("7.5"))
        self.assertEqual(self.settings.monthly_term_rate, Decimal("2.5"))


    def test_blank_percentage_values_are_saved_as_zero(self):
        response = self.client.post(reverse("save_price_list_settings"), {
            "profit_rate": "",
            "discount_rate": "",
            "monthly_term_rate": "",
            "usd_try": "41",
            "eur_try": "46",
            "changed_field": "profit_rate",
        })

        self.assertEqual(response.status_code, 200)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.profit_rate, Decimal("0"))
        self.assertEqual(self.settings.discount_rate, Decimal("0"))
        self.assertEqual(self.settings.monthly_term_rate, Decimal("0"))

    def test_discount_is_rejected_when_profit_is_zero(self):
        response = self.client.post(reverse("save_price_list_settings"), {
            "profit_rate": "0",
            "discount_rate": "10",
            "monthly_term_rate": "2",
            "usd_try": "41",
            "eur_try": "46",
            "changed_field": "discount_rate",
        })

        self.assertEqual(response.status_code, 400)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.profit_rate, Decimal("20"))
        self.assertEqual(self.settings.discount_rate, Decimal("5"))

    def test_product_code_links_to_product_card_detail(self):
        product = UrunKod.objects.create(kod="CLICKABLE-PRICE", urun_tipi="DIGER")
        card, _ = ProductCard.objects.get_or_create(urun=product)

        response = self.client.get(reverse("price_list"))

        self.assertContains(response, reverse("product_card_detail", args=[card.pk]))

    def test_real_profit_rate_is_calculated_after_profit_and_discount(self):
        response = self.client.post(reverse("save_price_list_settings"), {
            "profit_rate": "25",
            "discount_rate": "25",
            "monthly_term_rate": "2",
            "usd_try": "41",
            "eur_try": "46",
            "changed_field": "discount_rate",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["real_profit_rate"], "-6.25")

    def test_price_list_status_only_hides_card_from_price_list(self):
        product = UrunKod.objects.create(kod="ONLY-PRICE-LIST", urun_tipi="DIGER")
        card, _ = ProductCard.objects.get_or_create(urun=product)
        response = self.client.post(reverse("toggle_price_list_status"), {
            "card_id": card.pk, "active": "0", "return_status": "aktif",
        })
        self.assertEqual(response.status_code, 302)
        card.refresh_from_db()
        product.refresh_from_db()
        self.assertFalse(card.price_list_active)
        self.assertTrue(product.aktif)
        self.assertNotContains(self.client.get(reverse("price_list")), "ONLY-PRICE-LIST")
        self.assertContains(self.client.get(reverse("price_list") + "?durum=pasif"), "ONLY-PRICE-LIST")

    def test_excel_contains_only_active_price_list_cards(self):
        active_product = UrunKod.objects.create(kod="EXCEL-ACTIVE", urun_tipi="DIGER")
        ProductCard.objects.get_or_create(urun=active_product)
        passive_product = UrunKod.objects.create(kod="EXCEL-PASSIVE", urun_tipi="DIGER")
        ProductCard.objects.create(urun=passive_product, price_list_active=False)
        response = self.client.get(reverse("export_price_list_excel"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertIn(b"PK", response.content[:4])


    def test_price_list_passive_page_does_not_hide_card_by_general_product_status(self):
        product = UrunKod.objects.create(kod="7042-TEST", urun_tipi="DIGER", aktif=False)
        ProductCard.objects.create(urun=product, price_list_active=False)

        response = self.client.get(reverse("price_list") + "?durum=pasif")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "7042-TEST")


class ShowroomStatusToggleTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "showroom-status-manager", password="test-password"
        )
        patron, _ = Group.objects.get_or_create(name="patron")
        self.manager.groups.add(patron)
        self.client.force_login(self.manager)
        self.customer = Musteri.objects.create(ad="Föy Test Müşterisi")
        product = UrunKod.objects.create(kod="STATUS-TEST", urun_tipi="DIGER")
        card, _ = ProductCard.objects.get_or_create(urun=product)
        self.draft = ShowroomDraft.objects.create(
            created_by=self.manager, customer=self.customer, status="PENDING"
        )
        ShowroomDraftItem.objects.create(
            draft=self.draft,
            product_card=card,
            color="Siyah",
            size="M",
            quantity=1,
            unit_price=Decimal("100.00"),
        )

    def test_pending_draft_can_be_approved(self):
        response = self.client.post(
            reverse("showroom_toggle_approval", args=[self.draft.pk])
        )

        self.assertRedirects(
            response, reverse("showroom_detail_page", args=[self.draft.pk])
        )
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "APPROVED")

    def test_vat_is_calculated_after_discount(self):
        self.draft.discount_rate = Decimal("10.00")
        self.draft.vat_rate = Decimal("20.00")
        self.draft.save(update_fields=["discount_rate", "vat_rate", "updated_at"])

        response = self.client.get(
            reverse("showroom_archive_list"), {"kind": "draft"}
        )

        self.assertEqual(response.status_code, 200)
        summary = response.json()["items"][0]
        self.assertEqual(summary["subtotal"], "100.00")
        self.assertEqual(summary["discount"], "10.00")
        self.assertEqual(summary["vat_rate"], "20.00")
        self.assertEqual(summary["vat"], "18.00")
        self.assertEqual(summary["total"], "108.00")

    def test_order_taken_by_is_shown_on_folio_detail(self):
        self.draft.order_taken_by = "Mehmet Şener"
        self.draft.save(update_fields=["order_taken_by", "updated_at"])

        response = self.client.get(
            reverse("showroom_detail_page", args=[self.draft.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Siparişi Alan")
        self.assertContains(response, "Mehmet Şener")

    def test_previous_balance_is_added_after_vat(self):
        self.draft.discount_rate = Decimal("10.00")
        self.draft.vat_rate = Decimal("20.00")
        self.draft.previous_balance = Decimal("50.00")
        self.draft.save(
            update_fields=["discount_rate", "vat_rate", "previous_balance", "updated_at"]
        )

        response = self.client.get(
            reverse("showroom_archive_list"), {"kind": "draft"}
        )

        summary = response.json()["items"][0]
        self.assertEqual(summary["folio_total"], "108.00")
        self.assertEqual(summary["previous_balance"], "50.00")
        self.assertEqual(summary["total"], "158.00")
        self.assertEqual(summary["remaining"], "158.00")

    def test_folio_vat_rate_is_transferred_to_created_order(self):
        self.draft.status = "APPROVED"
        self.draft.vat_rate = Decimal("20.00")
        self.draft.save(update_fields=["status", "vat_rate", "updated_at"])

        response = self.client.post(
            reverse("showroom_transfer_create", args=[self.draft.pk])
        )

        self.assertRedirects(response, reverse("order_list"))
        order = Order.objects.get(urun_kodu="STATUS-TEST")
        self.assertEqual(order.satis_fiyati, Decimal("100.00"))
        self.assertEqual(order.vat_rate, Decimal("20.00"))

    def test_approved_draft_can_be_moved_back_to_pending(self):
        self.draft.status = "APPROVED"
        self.draft.save(update_fields=["status", "updated_at"])

        response = self.client.post(
            reverse("showroom_toggle_approval", args=[self.draft.pk])
        )

        self.assertRedirects(
            response, reverse("showroom_detail_page", args=[self.draft.pk])
        )
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "PENDING")

    def test_empty_pending_draft_cannot_be_approved(self):
        self.draft.items.all().delete()

        response = self.client.post(
            reverse("showroom_toggle_approval", args=[self.draft.pk])
        )

        self.assertEqual(response.status_code, 400)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "PENDING")

    def test_transferred_draft_remains_in_approved_archive(self):
        self.draft.status = "TRANSFERRED"
        self.draft.save(update_fields=["status", "updated_at"])

        response = self.client.get(
            reverse("showroom_archive_list"), {"kind": "approved"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["id"], self.draft.id)
        self.assertEqual(response.json()["items"][0]["status"], "TRANSFERRED")

    def test_transferred_draft_detail_and_print_remain_accessible(self):
        self.draft.status = "TRANSFERRED"
        self.draft.orders_created = True
        self.draft.save(update_fields=["status", "orders_created", "updated_at"])

        detail = self.client.get(
            reverse("showroom_detail_page", args=[self.draft.pk])
        )
        printed = self.client.get(
            reverse("showroom_print_page", args=[self.draft.pk])
        )

        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Siparişe Aktarıldı")
        self.assertContains(detail, "Taslağa Çevir")
        self.assertContains(detail, "Düzenle")
        self.assertContains(detail, "Sil")
        self.assertNotContains(detail, "Siparişleri Oluştur")
        self.assertEqual(printed.status_code, 200)
        self.assertContains(printed, "Siparişe Aktarıldı")

    def test_transferred_draft_can_be_moved_back_to_pending_and_edited(self):
        self.draft.status = "TRANSFERRED"
        self.draft.orders_created = True
        self.draft.save(update_fields=["status", "orders_created", "updated_at"])

        edit_response = self.client.get(
            reverse("showroom_edit_page", args=[self.draft.pk])
        )
        toggle_response = self.client.post(
            reverse("showroom_toggle_approval", args=[self.draft.pk])
        )

        self.assertEqual(edit_response.status_code, 200)
        self.assertRedirects(
            toggle_response, reverse("showroom_detail_page", args=[self.draft.pk])
        )
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "PENDING")
        self.assertTrue(self.draft.orders_created)

    def test_previously_transferred_folio_cannot_create_orders_again(self):
        self.draft.status = "APPROVED"
        self.draft.orders_created = True
        self.draft.save(update_fields=["status", "orders_created", "updated_at"])

        response = self.client.post(
            reverse("showroom_transfer_create", args=[self.draft.pk])
        )

        self.assertRedirects(
            response, reverse("showroom_detail_page", args=[self.draft.pk])
        )
        self.assertFalse(Order.objects.filter(urun_kodu="STATUS-TEST").exists())

    def test_customer_page_links_to_customer_folios(self):
        response = self.client.get(
            reverse("customer_detail_report", args=[self.customer.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, reverse("showroom_customer_folios", args=[self.customer.pk])
        )

    def test_customer_folios_are_filtered_and_clickable(self):
        other_customer = Musteri.objects.create(ad="Başka Müşteri")
        ShowroomDraft.objects.create(
            created_by=self.manager,
            customer=other_customer,
            status="APPROVED",
        )

        response = self.client.get(
            reverse("showroom_customer_folios", args=[self.customer.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Föy Test Müşterisi")
        self.assertContains(
            response, reverse("showroom_detail_page", args=[self.draft.pk])
        )
        self.assertNotContains(response, "Başka Müşteri")

    def test_customer_folios_popup_data_contains_current_prices(self):
        other_customer = Musteri.objects.create(ad="Popup Dışındaki Müşteri")
        ShowroomDraft.objects.create(
            created_by=self.manager,
            customer=other_customer,
            status="APPROVED",
        )

        response = self.client.get(
            reverse("showroom_customer_folios_data", args=[self.customer.pk])
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["customer"]["name"], "Föy Test Müşterisi")
        self.assertEqual([folio["id"] for folio in data["folios"]], [self.draft.pk])
        self.assertEqual(data["folios"][0]["items"][0]["urun_kodu"], "STATUS-TEST")
        self.assertEqual(data["folios"][0]["items"][0]["anlasilan_fiyat"], "100.00")

    def test_customer_base_price_size_is_saved_for_pricing_customer(self):
        pricing_customer = Musteri.objects.create(ad="MODAZEHRADA")
        self.assertTrue(
            CustomerPricingRule.objects.filter(customer=pricing_customer, active=True).exists()
        )

        response = self.client.post(
            reverse("showroom_draft_autosave"),
            data=json.dumps({
                "customer_id": pricing_customer.pk,
                "items": [{
                    "urun_kodu": "STATUS-TEST",
                    "anlasilan_fiyat": "10000",
                    "satirlar": [{
                        "renk": "Siyah",
                        "bedenler": ["BAZ FİYAT (BEDENSİZ)"],
                        "adet": 1,
                        "aciklama": "",
                    }],
                }],
                "payments": [],
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        saved_item = ShowroomDraftItem.objects.get(
            draft__created_by=self.manager,
            draft__status="DRAFT",
        )
        self.assertEqual(saved_item.size, "BAZ FİYAT (BEDENSİZ)")
        self.assertEqual(saved_item.unit_price, Decimal("10000"))

    def test_customer_base_price_size_is_rejected_for_regular_customer(self):
        response = self.client.post(
            reverse("showroom_draft_autosave"),
            data=json.dumps({
                "customer_id": self.customer.pk,
                "items": [{
                    "urun_kodu": "STATUS-TEST",
                    "anlasilan_fiyat": "10000",
                    "satirlar": [{
                        "renk": "Siyah",
                        "bedenler": ["BAZ FİYAT (BEDENSİZ)"],
                        "adet": 1,
                        "aciklama": "",
                    }],
                }],
                "payments": [],
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("yalnızca özel fiyat", response.json()["message"])
        self.assertFalse(
            ShowroomDraft.objects.filter(created_by=self.manager, status="DRAFT").exists()
        )

    def test_customer_base_price_rows_cannot_be_transferred_as_real_orders(self):
        self.draft.status = "APPROVED"
        self.draft.save(update_fields=["status", "updated_at"])
        self.draft.items.update(size="BAZ FİYAT (BEDENSİZ)")

        preview = self.client.get(
            reverse("showroom_transfer_preview", args=[self.draft.pk])
        )
        response = self.client.post(
            reverse("showroom_transfer_create", args=[self.draft.pk])
        )

        self.assertContains(preview, "doğrudan siparişe aktarılamaz")
        self.assertContains(preview, "disabled")
        self.assertRedirects(
            response, reverse("showroom_transfer_preview", args=[self.draft.pk])
        )
        self.assertFalse(Order.objects.filter(urun_kodu="STATUS-TEST").exists())

    def test_latest_approved_customer_folio_base_price_is_returned(self):
        pricing_customer = Musteri.objects.create(ad="MODAZEHRADA")
        card = self.draft.items.first().product_card
        now = timezone.now()

        older = ShowroomDraft.objects.create(
            created_by=self.manager,
            customer=pricing_customer,
            status="APPROVED",
        )
        ShowroomDraftItem.objects.create(
            draft=older,
            product_card=card,
            color="Siyah",
            size="BAZ FİYAT (BEDENSİZ)",
            quantity=1,
            unit_price=Decimal("9000"),
        )
        ShowroomDraft.objects.filter(pk=older.pk).update(updated_at=now - timedelta(days=2))

        latest = ShowroomDraft.objects.create(
            created_by=self.manager,
            customer=pricing_customer,
            status="TRANSFERRED",
        )
        ShowroomDraftItem.objects.create(
            draft=latest,
            product_card=card,
            color="Siyah",
            size="BAZ FİYAT (BEDENSİZ)",
            quantity=1,
            unit_price=Decimal("10000"),
        )
        ShowroomDraft.objects.filter(pk=latest.pk).update(updated_at=now - timedelta(days=1))

        pending = ShowroomDraft.objects.create(
            created_by=self.manager,
            customer=pricing_customer,
            status="PENDING",
        )
        ShowroomDraftItem.objects.create(
            draft=pending,
            product_card=card,
            color="Siyah",
            size="BAZ FİYAT (BEDENSİZ)",
            quantity=1,
            unit_price=Decimal("12000"),
        )

        response = self.client.get(
            reverse("showroom_customer_product_base_price"),
            {"customer_id": pricing_customer.pk, "product_code": "status-test"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["found"])
        self.assertEqual(data["base_price"], "10000.00")
        self.assertEqual(data["folio_id"], latest.pk)

    def test_customer_folio_base_price_reports_missing_product(self):
        pricing_customer = Musteri.objects.create(ad="MODAZEHRADA")

        response = self.client.get(
            reverse("showroom_customer_product_base_price"),
            {"customer_id": pricing_customer.pk, "product_code": "UNKNOWN"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["applies"])
        self.assertFalse(response.json()["found"])
