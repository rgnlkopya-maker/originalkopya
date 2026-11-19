"""Product-code-only link from order detail to the matching product album."""
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

from core.models import GalleryAlbum, Order


@override_settings(
    SECURE_SSL_REDIRECT=False,
    MIDDLEWARE=[middleware for middleware in settings.MIDDLEWARE
                if middleware != "app_settings.middleware.MoliAccessMiddleware"],
)
class OrderAlbumLinkTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="order-album-test-manager", password="test-password"
        )
        role, _ = Group.objects.get_or_create(name="patron")
        self.user.groups.add(role)
        self.client.force_login(self.user)

    @patch("core.signals_qr.ensure_order_qr")
    def test_product_code_opens_matching_album_directly(self, _qr):
        album = GalleryAlbum.objects.create(code="7119")
        order = Order.objects.create(siparis_tipi="SERI", urun_kodu="7119")
        response = self.client.get(f"/order/{order.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ürün Albümü")
        self.assertContains(response, f'href="/urun-albumu/?album={album.pk}"')
        self.assertNotContains(response, "photos.app.goo.gl")

    @patch("core.signals_qr.ensure_order_qr")
    def test_album_link_updates_when_order_product_code_changes(self, _qr):
        first = GalleryAlbum.objects.create(code="7119")
        second = GalleryAlbum.objects.create(code="8120")
        order = Order.objects.create(siparis_tipi="OZEL", urun_kodu="7119")
        first_response = self.client.get(f"/order/{order.pk}/")
        self.assertContains(first_response, f'href="/urun-albumu/?album={first.pk}"')
        order.urun_kodu = "8120"
        order.save(update_fields=["urun_kodu"])
        second_response = self.client.get(f"/order/{order.pk}/")
        self.assertContains(second_response, f'href="/urun-albumu/?album={second.pk}"')
        self.assertNotContains(second_response, f'href="/urun-albumu/?album={first.pk}"')

    @patch("core.signals_qr.ensure_order_qr")
    def test_unlisted_product_opens_filtered_gallery_and_blank_code_has_no_link(self, _qr):
        order = Order.objects.create(siparis_tipi="TEKLI", urun_kodu="NO-ALBUM-42")
        response = self.client.get(f"/order/{order.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/urun-albumu/?q=NO-ALBUM-42"')
        order.urun_kodu = ""
        order.save(update_fields=["urun_kodu"])
        empty_response = self.client.get(f"/order/{order.pk}/")
        self.assertNotContains(empty_response, 'class="order-album-link no-print"')
