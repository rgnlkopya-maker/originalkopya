from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from .models import Musteri, Order, OrderEvent, UrunKod
from .qr import ensure_order_qr


class OrderModelTests(TestCase):
    def test_ozel_siparis_property_uses_database_value(self):
        order = Order(siparis_tipi="OZEL")
        self.assertTrue(order.is_ozel_siparis)

    def test_empty_order_type_can_generate_fallback_number(self):
        order = Order.objects.create(siparis_tipi=None)
        self.assertEqual(order.siparis_numarasi, "SP0001")

    def test_order_uses_product_code_default_type_when_empty(self):
        UrunKod.objects.create(kod="7119", urun_tipi="BALIK")
        order = Order.objects.create(siparis_tipi="SERI", urun_kodu="7119")
        self.assertEqual(order.urun_tipi, "BALIK")

    def test_manual_order_type_overrides_product_code_default(self):
        UrunKod.objects.create(kod="7119", urun_tipi="BALIK")
        order = Order.objects.create(
            siparis_tipi="SERI", urun_kodu="7119", urun_tipi="HELEN"
        )
        self.assertEqual(order.urun_tipi, "HELEN")

    def test_tekli_order_generates_tekli_number(self):
        order = Order.objects.create(siparis_tipi="TEKLI")
        self.assertTrue(order.is_tekli_siparis)
        self.assertEqual(order.siparis_numarasi, "TEKLI0001")


class OrderQrTests(TestCase):
    @override_settings(
        BASE_URL="https://example.test",
        SUPABASE_BUCKET_NAME="custom-order-qr",
    )
    @patch("core.qr.qrcode.make")
    @patch("core.qr.get_supabase")
    def test_qr_uses_order_detail_route_and_configured_bucket(
        self, get_supabase, make_qr
    ):
        bucket = Mock()
        bucket.get_public_url.return_value = "https://cdn.example.test/order.png"
        supabase = Mock()
        supabase.storage.from_.return_value = bucket
        get_supabase.return_value = supabase
        make_qr.return_value.save.side_effect = (
            lambda buffer, format: buffer.write(b"\x89PNG")
        )

        Order.objects.bulk_create([Order(siparis_tipi="OZEL", siparis_numarasi="OZEL0001")])
        order = Order.objects.get(siparis_numarasi="OZEL0001")
        url = ensure_order_qr(order)

        self.assertEqual(url, "https://cdn.example.test/order.png")
        make_qr.assert_called_once_with(
            f"https://example.test/order/{order.pk}/"
        )
        supabase.storage.from_.assert_called_with("custom-order-qr")
        uploaded_bytes = bucket.upload.call_args.args[1]
        self.assertTrue(uploaded_bytes.startswith(b"\x89PNG"))


class MultiOrderCreateTests(TestCase):
    @patch("core.signals_qr.ensure_order_qr")
    def test_multi_order_create_does_not_call_a_second_qr_implementation(
        self, ensure_order_qr
    ):
        user = get_user_model().objects.create_user("manager", password="test")
        patron, _ = Group.objects.get_or_create(name="patron")
        user.groups.add(patron)
        self.client.force_login(user)
        musteri = Musteri.objects.create(ad="Test Müşteri")

        response = self.client.post(
            "/orders/multi-create/",
            {
                "siparis_tipi": "SERI",
                "musteri": str(musteri.pk),
                "urun_kodu": "TEST-01",
                "urun_tipi": "ETEKLI_BALIK",
                "renk_row_0": "BEYAZ",
                "beden_row_0[]": ["38"],
                "adet_row_0": "2",
                "para_birimi": "TRY",
                "maliyet_para_birimi": "TRY",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 2)
        self.assertFalse(Order.objects.exclude(urun_tipi="ETEKLI_BALIK").exists())
        self.assertEqual(ensure_order_qr.call_count, 2)


class OrderListDescriptionTests(TestCase):
    @patch("core.signals_qr.ensure_order_qr")
    def test_long_description_is_shortened_and_available_in_popover(self, _qr):
        user = get_user_model().objects.create_user("list-user", password="test")
        self.client.force_login(user)
        Order.objects.create(
            siparis_tipi="SERI",
            aciklama="Kutusunda özel etiket kullanılacak",
        )

        response = self.client.get("/")

        self.assertContains(response, "Kutusunda …")
        self.assertContains(response, 'data-bs-title="Açıklama"')
        self.assertContains(response, "Kutusunda özel etiket kullanılacak")


class DeleteOrderEventTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("patron-test", password="test")
        patron, _ = Group.objects.get_or_create(name="patron")
        self.user.groups.add(patron)
        self.client.force_login(self.user)

    @patch("core.signals_qr.ensure_order_qr")
    def test_deleting_shipped_event_restores_previous_shipping_state(self, _qr):
        order = Order.objects.create(siparis_tipi="SERI", sevkiyat_durum="gonderildi")
        OrderEvent.objects.create(
            order=order,
            user=self.user.username,
            stage="sevkiyat_durum",
            value="hazirlaniyor",
        )
        shipped = OrderEvent.objects.create(
            order=order,
            user=self.user.username,
            stage="sevkiyat_durum",
            value="gonderildi",
        )

        response = self.client.post(f"/events/{shipped.id}/delete/")

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.sevkiyat_durum, "hazirlaniyor")
        list_response = self.client.get("/")
        self.assertEqual(list_response.context["sevke_count"], 0)

    @patch("core.signals_qr.ensure_order_qr")
    def test_deleting_only_shipping_event_restores_default_state(self, _qr):
        order = Order.objects.create(siparis_tipi="SERI", sevkiyat_durum="gonderildi")
        shipped = OrderEvent.objects.create(
            order=order,
            user=self.user.username,
            stage="sevkiyat_durum",
            value="gonderildi",
        )

        self.client.post(f"/events/{shipped.id}/delete/")

        order.refresh_from_db()
        self.assertEqual(order.sevkiyat_durum, "bekliyor")

# Create your tests here.
