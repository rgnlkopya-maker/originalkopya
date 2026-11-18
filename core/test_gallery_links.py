"""Regression checks for the simplified Google Photos album gallery."""
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from core.models import GalleryAlbum


@override_settings(SECURE_SSL_REDIRECT=False)
class GalleryLinksPermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(username="gallery-manager", password="test-password")
        manager_group, _ = Group.objects.get_or_create(name="mudur")
        self.manager.groups.add(manager_group)
        self.staff = User.objects.create_user(username="gallery-staff", password="test-password")
        self.album = GalleryAlbum.objects.create(code="7119")

    def test_manager_sees_overlay_and_can_open_edit_form(self):
        self.client.force_login(self.manager)
        response = self.client.get("/urun-albumu/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="album-edit-overlay"')
        self.assertNotContains(response, "Albüm Ekle")
        self.assertNotContains(response, "Kapak ve bağlantıyı düzenle")
        edit = self.client.get(f"/urun-albumu/?album={self.album.pk}")
        self.assertEqual(edit.status_code, 200)
        self.assertContains(edit, 'name="google_photos_url"')
        self.assertContains(edit, 'name="cover"')

    def test_staff_cannot_see_or_access_album_editing(self):
        self.client.force_login(self.staff)
        response = self.client.get("/urun-albumu/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="album-edit-overlay"')
        self.assertEqual(self.client.get(f"/urun-albumu/?album={self.album.pk}").status_code, 403)
        self.assertEqual(
            self.client.post(
                f"/urun-albumu/{self.album.pk}/baglanti/",
                {"google_photos_url": "https://photos.app.goo.gl/example"},
            ).status_code,
            403,
        )
        self.album.refresh_from_db()
        self.assertEqual(self.album.google_photos_url, "")

    def test_manager_saves_google_photos_link_and_cover_in_database(self):
        self.client.force_login(self.manager)
        buffer = BytesIO()
        Image.new("RGB", (80, 100), (125, 90, 140)).save(buffer, format="PNG")
        cover = SimpleUploadedFile("cover.png", buffer.getvalue(), content_type="image/png")
        response = self.client.post(
            f"/urun-albumu/{self.album.pk}/baglanti/",
            {"google_photos_url": "https://photos.app.goo.gl/example", "cover": cover},
        )
        self.assertEqual(response.status_code, 302)
        self.album.refresh_from_db()
        self.assertEqual(self.album.google_photos_url, "https://photos.app.goo.gl/example")
        self.assertTrue(self.album.cover_data_url.startswith("data:image/jpeg;base64,"))
        listing = self.client.get("/urun-albumu/")
        self.assertContains(listing, 'target="_blank" rel="noopener noreferrer"')
        self.assertContains(listing, "https://photos.app.goo.gl/example")

    def test_manager_cannot_save_non_google_url(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            f"/urun-albumu/{self.album.pk}/baglanti/",
            {"google_photos_url": "https://example.com/album"},
        )
        self.assertEqual(response.status_code, 302)
        self.album.refresh_from_db()
        self.assertEqual(self.album.google_photos_url, "")
