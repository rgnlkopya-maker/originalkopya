"""Product gallery tabs, note management and role access."""
import base64
from io import BytesIO
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from core.models import GalleryAlbum, GalleryGroup


@override_settings(SECURE_SSL_REDIRECT=False,
 MIDDLEWARE=[m for m in settings.MIDDLEWARE if m != "app_settings.middleware.MoliAccessMiddleware"])
class GalleryLinksTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user("gallery-manager", password="test")
        role, _ = Group.objects.get_or_create(name="mudur")
        self.manager.groups.add(role)
        self.staff = User.objects.create_user("gallery-staff", password="test")
        self.album = GalleryAlbum.objects.create(code="7119")

    def test_staff_reads_plain_photo_and_notes(self):
        self.client.force_login(self.staff)
        result = self.client.get(f"/urun-albumu/?album={self.album.pk}")
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, ">Standart</a>")
        self.assertContains(result, "Üretim Notları")
        self.assertNotContains(result, "Tek kapak fotoğrafı")
        self.assertNotContains(result, "+ Müşteri Ekle")
        self.assertNotContains(result, 'name="google_photos_url"')

    def test_manager_creates_customer_photo_link_note(self):
        self.client.force_login(self.manager)
        created = self.client.post(f"/urun-albumu/{self.album.pk}/musteri-ekle/", {"name":"Lara"})
        self.assertEqual(created.status_code, 302)
        group = GalleryGroup.objects.get(album=self.album, name="Lara")
        buffer=BytesIO()
        Image.new("RGB", (80,100),(90,40,120)).save(buffer,"PNG")
        upload=SimpleUploadedFile("cover.png",buffer.getvalue(),content_type="image/png")
        response=self.client.post(f"/urun-albumu/grup/{group.pk}/baglanti/",
            {"google_photos_url":"https://photos.app.goo.gl/test", "production_notes":"Yaka 2 cm daha yuksek", "cover":upload})
        self.assertEqual(response.status_code,302)
        group.refresh_from_db()
        self.assertTrue(group.cover_data_url.startswith("data:image/jpeg;base64,"))
        self.assertEqual(group.production_notes,"Yaka 2 cm daha yuksek")
        detail=self.client.get(f"/urun-albumu/?album={self.album.pk}&group={group.pk}")
        self.assertContains(detail,"Yaka 2 cm daha yuksek")
        self.assertContains(detail,'href="https://photos.app.goo.gl/test"')
        self.assertNotContains(detail, "Tek kapak fotoğrafı")

    def test_staff_cannot_modify_or_add(self):
        self.client.force_login(self.staff)
        self.client.get(f"/urun-albumu/?album={self.album.pk}")
        group=GalleryGroup.objects.get(album=self.album,name="Standart Model")
        self.assertEqual(self.client.get(f"/urun-albumu/?album={self.album.pk}&edit=1").status_code,403)
        self.assertEqual(self.client.post(f"/urun-albumu/{self.album.pk}/musteri-ekle/",{"name":"Lara"}).status_code,403)
        self.assertEqual(self.client.post(f"/urun-albumu/grup/{group.pk}/baglanti/",{"production_notes":"x"}).status_code,403)

    def test_existing_standard_album_data_preserved(self):
        self.album.cover_data_url = "data:image/jpeg;base64,"+base64.b64encode(b"test").decode()
        self.album.google_photos_url = "https://photos.app.goo.gl/existing"
        self.album.save(update_fields=["cover_data_url","google_photos_url"])
        self.client.force_login(self.manager)
        self.client.get(f"/urun-albumu/?album={self.album.pk}")
        group=GalleryGroup.objects.get(album=self.album,name="Standart Model")
        self.assertEqual(group.cover_data_url,self.album.cover_data_url)
        self.assertEqual(group.google_photos_url,self.album.google_photos_url)

    def test_index_loads_cover_lazily_and_supports_etag(self):
        self.album.cover_data_url="data:image/jpeg;base64,"+base64.b64encode(b"image").decode()
        self.album.save(update_fields=["cover_data_url"])
        self.client.force_login(self.manager)
        listing=self.client.get("/urun-albumu/")
        self.assertContains(listing, "gallery-lazy-cover")
        self.assertNotContains(listing, "data:image/jpeg;base64,")
        image=self.client.get(f"/urun-albumu/{self.album.pk}/kapak/")
        self.assertEqual(image.status_code,200)
        self.assertEqual(image.content,b"image")
        self.assertEqual(self.client.get(f"/urun-albumu/{self.album.pk}/kapak/",HTTP_IF_NONE_MATCH=image["ETag"]).status_code,304)

    def test_invalid_url_does_not_save(self):
        self.client.force_login(self.manager)
        self.client.get(f"/urun-albumu/?album={self.album.pk}")
        group=GalleryGroup.objects.get(album=self.album,name="Standart Model")
        result=self.client.post(f"/urun-albumu/grup/{group.pk}/baglanti/",
            {"google_photos_url":"https://example.com","production_notes":"x"})
        self.assertEqual(result.status_code,302)
        group.refresh_from_db()
        self.assertEqual(group.google_photos_url,"")

    def test_legacy_standard_save_remains_functional(self):
        self.client.force_login(self.manager)
        response=self.client.post(f"/urun-albumu/{self.album.pk}/baglanti/",
            {"google_photos_url":"https://photos.app.goo.gl/example"})
        self.assertEqual(response.status_code,302)
        self.album.refresh_from_db()
        self.assertEqual(self.album.google_photos_url,"https://photos.app.goo.gl/example")
        self.assertEqual(GalleryGroup.objects.get(album=self.album,name="Standart Model").google_photos_url,self.album.google_photos_url)
