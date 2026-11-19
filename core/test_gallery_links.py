"""Product gallery tabs, note management and role access."""
import base64
from io import BytesIO
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from core.models import GalleryAlbum, GalleryGroup, GalleryProductionNote, Musteri


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
        customer = Musteri.objects.create(ad="Lara", aktif=True)
        created = self.client.post(f"/urun-albumu/{self.album.pk}/musteri-ekle/", {"customer_id":str(customer.pk)})
        self.assertEqual(created.status_code, 302)
        group = GalleryGroup.objects.get(album=self.album, name="Lara")
        buffer=BytesIO()
        Image.new("RGB", (80,100),(90,40,120)).save(buffer,"PNG")
        upload=SimpleUploadedFile("cover.png",buffer.getvalue(),content_type="image/png")
        response=self.client.post(f"/urun-albumu/grup/{group.pk}/baglanti/",
            {"google_photos_url":"https://photos.app.goo.gl/test", "cover":upload})
        self.assertEqual(response.status_code,302)
        group.refresh_from_db()
        self.assertTrue(group.cover_data_url.startswith("data:image/jpeg;base64,"))
        self.assertEqual(group.production_notes,"")
        added=self.client.post(f"/urun-albumu/grup/{group.pk}/not-ekle/",
                               {"body":"Yaka 2 cm daha yuksek"})
        self.assertEqual(added.status_code,302)
        self.assertEqual(GalleryProductionNote.objects.get(group=group).body,"Yaka 2 cm daha yuksek")
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

    def test_regular_user_can_append_notes_but_cannot_erase_existing_notes(self):
        self.client.force_login(self.staff)
        self.client.get(f"/urun-albumu/?album={self.album.pk}")
        group=GalleryGroup.objects.get(album=self.album,name="Standart Model")
        first=self.client.post(f"/urun-albumu/grup/{group.pk}/not-ekle/",
                               {"body":"Dikimde dikkat edilecek"})
        self.assertEqual(first.status_code,302)
        second=self.client.post(f"/urun-albumu/grup/{group.pk}/not-ekle/",
                                {"body":"Etek boyu kontrol edilsin"})
        self.assertEqual(second.status_code,302)
        self.assertEqual(GalleryProductionNote.objects.filter(group=group,deleted_at__isnull=True).count(),2)
        record=GalleryProductionNote.objects.get(group=group,body="Dikimde dikkat edilecek")
        self.assertEqual(record.created_by,self.staff)
        attempt=self.client.post(f"/urun-albumu/not/{record.pk}/sil/")
        self.assertEqual(attempt.status_code,403)
        record.refresh_from_db()
        self.assertIsNone(record.deleted_at)
        response=self.client.get(f"/urun-albumu/?album={self.album.pk}&group={group.pk}")
        self.assertContains(response,"Dikimde dikkat edilecek")
        self.assertContains(response,"Etek boyu kontrol edilsin")
        self.assertContains(response,'name="body"')
        self.assertNotContains(response,'class="note-delete"')
        self.assertNotContains(response,'name="production_notes"')

    def test_manager_can_hide_individual_note_without_destroying_its_content(self):
        self.client.force_login(self.manager)
        self.client.get(f"/urun-albumu/?album={self.album.pk}")
        group=GalleryGroup.objects.get(album=self.album,name="Standart Model")
        a=GalleryProductionNote.objects.create(group=group,body="Ilk not",created_by=self.staff)
        b=GalleryProductionNote.objects.create(group=group,body="Ikinci not",created_by=self.manager)
        response=self.client.post(f"/urun-albumu/not/{a.pk}/sil/")
        self.assertEqual(response.status_code,302)
        a.refresh_from_db()
        self.assertIsNotNone(a.deleted_at)
        self.assertEqual(a.deleted_by,self.manager)
        self.assertEqual(a.body,"Ilk not")
        page=self.client.get(f"/urun-albumu/?album={self.album.pk}")
        self.assertNotContains(page,"Ilk not")
        self.assertContains(page,"Ikinci not")
        self.assertContains(page,'class="note-delete"')
        self.assertIsNone(GalleryProductionNote.objects.get(pk=b.pk).deleted_at)

    def test_manager_cover_save_cannot_modify_production_notes(self):
        self.client.force_login(self.manager)
        self.client.get(f"/urun-albumu/?album={self.album.pk}")
        group=GalleryGroup.objects.get(album=self.album,name="Standart Model")
        group.production_notes="Eski not korunacak"
        group.save(update_fields=["production_notes"])
        note=GalleryProductionNote.objects.create(group=group,body="Yeni not")
        self.client.post(f"/urun-albumu/grup/{group.pk}/baglanti/",
                         {"google_photos_url":"https://photos.app.goo.gl/test",
                          "production_notes":""})
        group.refresh_from_db()
        self.assertEqual(group.production_notes,"Eski not korunacak")
        self.assertEqual(GalleryProductionNote.objects.get(pk=note.pk).body,"Yeni not")

    def test_cover_overlay_removed_from_album_listing(self):
        self.client.force_login(self.manager)
        listing=self.client.get("/urun-albumu/")
        self.assertEqual(listing.status_code,200)
        self.assertNotContains(listing,'albümünü düzenle')
        detail=self.client.get(f"/urun-albumu/?album={self.album.pk}")
        self.assertContains(detail,"Sekmeyi düzenle")

    def test_other_patron_can_edit_covers_customer_tabs_and_delete_notes(self):
        User = get_user_model()
        patron = User.objects.create_user(
            username="other-patron", first_name="Ahmet", last_name="Yilmaz", password="test"
        )
        patron_group, _ = Group.objects.get_or_create(name="patron")
        patron.groups.add(patron_group)
        self.client.force_login(patron)
        listing = self.client.get("/urun-albumu/")
        self.assertEqual(listing.status_code, 200)
        self.client.get(f"/urun-albumu/?album={self.album.pk}")
        detail = self.client.get(f"/urun-albumu/?album={self.album.pk}")
        self.assertContains(detail, "Sekmeyi düzenle")
        self.assertContains(detail, "+ Müşteri Ekle")
        edit = self.client.get(f"/urun-albumu/?album={self.album.pk}&edit=1")
        self.assertEqual(edit.status_code, 200)
        standard = GalleryGroup.objects.get(album=self.album, name="Standart Model")
        save = self.client.post(
            f"/urun-albumu/grup/{standard.pk}/baglanti/",
            {"google_photos_url": "https://photos.app.goo.gl/otherPatron"}
        )
        self.assertEqual(save.status_code, 302)
        standard.refresh_from_db()
        self.assertEqual(standard.google_photos_url, "https://photos.app.goo.gl/otherPatron")
        existing = Musteri.objects.create(ad="Patron Modeli", aktif=True)
        customer = self.client.post(
            f"/urun-albumu/{self.album.pk}/musteri-ekle/", {"customer_id": str(existing.pk)}
        )
        self.assertEqual(customer.status_code, 302)
        note = GalleryProductionNote.objects.create(group=standard, body="Uretim notu")
        deleted = self.client.post(f"/urun-albumu/not/{note.pk}/sil/")
        self.assertEqual(deleted.status_code, 302)
        note.refresh_from_db()
        self.assertIsNotNone(note.deleted_at)

    def test_named_excluded_patrons_cannot_edit_or_delete_but_can_add_notes(self):
        User = get_user_model()
        patron_group, _ = Group.objects.get_or_create(name="patron")
        scenarios = [
            ("emine", "Emine", "Kanyış"),
            ("osmankanyis", "Osman", "Kanyış"),
            ("other-login-emine", "Emine", "Kanyis"),
            ("other-login-osman", "Osman", "Kanyış"),
        ]
        self.client.force_login(self.manager)
        self.client.get(f"/urun-albumu/?album={self.album.pk}")
        standard = GalleryGroup.objects.get(album=self.album, name="Standart Model")
        for username, first_name, last_name in scenarios:
            with self.subTest(username=username):
                person = User.objects.create_user(
                    username=username, first_name=first_name, last_name=last_name, password="test"
                )
                person.groups.add(patron_group)
                self.client.force_login(person)
                listing = self.client.get("/urun-albumu/")
                self.assertEqual(listing.status_code, 200)
                details = self.client.get(f"/urun-albumu/?album={self.album.pk}")
                self.assertEqual(details.status_code, 200)
                self.assertNotContains(details, "Sekmeyi düzenle")
                self.assertNotContains(details, "+ Müşteri Ekle")
                self.assertNotContains(details, 'class="note-delete"')
                self.assertEqual(
                    self.client.get(f"/urun-albumu/?album={self.album.pk}&edit=1").status_code, 403
                )
                self.assertEqual(
                    self.client.post(
                        f"/urun-albumu/grup/{standard.pk}/baglanti/",
                        {"google_photos_url": "https://photos.app.goo.gl/notAllowed"}
                    ).status_code, 403
                )
                self.assertEqual(
                    self.client.post(
                        f"/urun-albumu/{self.album.pk}/baglanti/",
                        {"google_photos_url": "https://photos.app.goo.gl/notAllowed"}
                    ).status_code, 403
                )
                self.assertEqual(
                    self.client.post(
                        f"/urun-albumu/{self.album.pk}/musteri-ekle/", {"name": "Yasak"}
                    ).status_code, 403
                )
                note = GalleryProductionNote.objects.create(
                    group=standard, body=f"{username} notu"
                )
                self.assertEqual(
                    self.client.post(f"/urun-albumu/not/{note.pk}/sil/").status_code, 403
                )
                note.refresh_from_db()
                self.assertIsNone(note.deleted_at)
                # The user remains able to contribute new production notes.
                self.assertEqual(
                    self.client.post(
                        f"/urun-albumu/grup/{standard.pk}/not-ekle/",
                        {"body": f"{username} yeni not"}
                    ).status_code, 302
                )
                self.assertTrue(
                    GalleryProductionNote.objects.filter(
                        group=standard, body=f"{username} yeni not", created_by=person
                    ).exists()
                )

    def test_exclusion_precedes_manager_group_and_superuser_status(self):
        User = get_user_model()
        excluded = User.objects.create_superuser(
            username="EmineKanyis", email="example@example.invalid", password="test"
        )
        manager_group, _ = Group.objects.get_or_create(name="mudur")
        excluded.groups.add(manager_group)
        self.client.force_login(excluded)
        self.assertEqual(
            self.client.get(f"/urun-albumu/?album={self.album.pk}&edit=1").status_code, 403
        )
        self.client.get(f"/urun-albumu/?album={self.album.pk}")
        standard = GalleryGroup.objects.get(album=self.album, name="Standart Model")
        note = GalleryProductionNote.objects.create(group=standard, body="Korunan not")
        self.assertEqual(
            self.client.post(f"/urun-albumu/not/{note.pk}/sil/").status_code, 403
        )

    def test_customer_add_form_is_outside_scrollable_tab_bar(self):
        """The customer input must not be clipped by horizontally scrolling tabs."""
        self.client.force_login(self.manager)
        response = self.client.get(f"/urun-albumu/?album={self.album.pk}")
        self.assertEqual(response.status_code, 200)
        markup = response.content.decode("utf-8")
        tab_start = markup.index('<nav class="tabs"')
        nav_end = markup.index("</nav>", tab_start)
        toggle = markup.index('id="galleryCustomerToggle"', tab_start)
        panel = markup.index('id="galleryCustomerPanel" hidden', tab_start)
        self.assertLess(toggle, nav_end)
        self.assertGreater(panel, nav_end)
        self.assertIn('aria-expanded="false"', markup)
        self.assertIn('.link-gallery .add-panel[hidden]{display:none!important}', markup)
        self.assertIn("customerPanel.hidden=!opening", markup)

        self.client.force_login(self.staff)
        staff_response = self.client.get(f"/urun-albumu/?album={self.album.pk}")
        self.assertNotContains(staff_response, 'id="galleryCustomerToggle"')
        self.assertNotContains(staff_response, 'id="galleryCustomerPanel"')

    def test_gallery_customer_select_uses_active_moliapp_customers_fresh_each_request(self):
        self.client.force_login(self.manager)
        before = self.client.get(f"/urun-albumu/?album={self.album.pk}")
        self.assertNotContains(before, "YENI-MUSTERI-2026")
        current = Musteri.objects.create(ad="YENI-MUSTERI-2026", aktif=True)
        inactive = Musteri.objects.create(ad="PASIF-MUSTERI-2026", aktif=False)
        after = self.client.get(f"/urun-albumu/?album={self.album.pk}")
        self.assertContains(after, f'<option value="{current.pk}">YENI-MUSTERI-2026</option>', html=True)
        self.assertNotContains(after, "PASIF-MUSTERI-2026")
        # This is a dropdown, not a second free-text customer register.
        self.assertContains(after, 'name="customer_id"')
        self.assertNotContains(after, 'name="name"')
        current.ad = "YENI-MUSTERI-GUNCEL"
        current.save(update_fields=["ad"])
        newer = self.client.get(f"/urun-albumu/?album={self.album.pk}")
        self.assertContains(newer, "YENI-MUSTERI-GUNCEL")
        self.assertNotContains(newer, "YENI-MUSTERI-2026")
        inactive.aktif = True
        inactive.save(update_fields=["aktif"])
        activated = self.client.get(f"/urun-albumu/?album={self.album.pk}")
        self.assertContains(activated, "PASIF-MUSTERI-2026")

    def test_customer_tab_add_requires_id_from_customer_registry_and_deduplicates(self):
        self.client.force_login(self.manager)
        current = Musteri.objects.create(ad="Sitare Yokus", aktif=True)
        path = f"/urun-albumu/{self.album.pk}/musteri-ekle/"
        for data in ({"name":"Uydurma Musteri"}, {"customer_id":"not-a-number"},
                     {"customer_id":"999999999"}, {"customer_id":""}):
            result=self.client.post(path, data)
            self.assertEqual(result.status_code, 302)
        self.assertFalse(GalleryGroup.objects.filter(album=self.album,name="Uydurma Musteri").exists())
        first = self.client.post(path, {"customer_id": str(current.pk)})
        second = self.client.post(path, {"customer_id": str(current.pk)})
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(GalleryGroup.objects.filter(album=self.album, name="Sitare Yokus").count(), 1)
        current.aktif = False
        current.save(update_fields=["aktif"])
        refused = self.client.post(path, {"customer_id": str(current.pk)})
        self.assertEqual(refused.status_code, 302)
        self.assertEqual(GalleryGroup.objects.filter(album=self.album, name="Sitare Yokus").count(), 1)
