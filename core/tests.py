from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from .models import Order
from .qr import ensure_order_qr


class OrderModelTests(TestCase):
    def test_ozel_siparis_property_uses_database_value(self):
        order = Order(siparis_tipi="OZEL")
        self.assertTrue(order.is_ozel_siparis)

    def test_empty_order_type_can_generate_fallback_number(self):
        order = Order.objects.create(siparis_tipi=None)
        self.assertEqual(order.siparis_numarasi, "SP0001")


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

# Create your tests here.
