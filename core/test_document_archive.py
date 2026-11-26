from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image
from storage3.exceptions import StorageApiError

from core.document_archive_models import ArchiveDocument, ArchiveFolder
from core.document_archive_views import BUCKET, _private_storage


def make_image():
    data = BytesIO()
    Image.new("RGB", (12, 16), "white").save(data, "JPEG")
    return data.getvalue()


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver"])
class ArchiveTest(TestCase):
    def setUp(self):
        user = get_user_model()
        self.owner = user.objects.create_user(username="archive-owner")
        self.owner.groups.add(Group.objects.create(name="patron"))
        self.mudur = user.objects.create_user(username="archive-mudur")
        self.mudur.groups.add(Group.objects.create(name="mudur"))
        self.staff = user.objects.create_user(username="archive-staff")
        self.client.force_login(self.owner)

    def test_root_nested_folder_and_duplicate(self):
        response = self.client.post(reverse("document_archive_create_folder"), {"name": "Sözleşmeler"}, follow=True)
        self.assertContains(response, "Evrak Arşivi")
        self.assertContains(response, "Sözleşmeler")
        self.assertContains(response, 'capture="environment"')
        self.assertIn("no-store", response["Cache-Control"])
        root = ArchiveFolder.objects.get(name="Sözleşmeler")
        response = self.client.post(reverse("document_archive_create_folder"), {"name": "sözleşmeler"}, follow=True)
        self.assertContains(response, "aynı isimde")
        self.client.post(reverse("document_archive_child", args=[root.pk]), {"name": "2026"})
        child = root.subfolders.get(name="2026")
        response = self.client.get(reverse("document_archive_folder", args=[child.pk]))
        self.assertContains(response, "Sözleşmeler")
        self.assertContains(response, "2026")

    @patch("core.document_archive_views._private_storage")
    def test_upload_and_retrieve_session_protected(self, storage):
        raw = make_image()
        folder = ArchiveFolder.objects.create(name="Faturalar", name_key="faturalar")
        url = reverse("document_archive_folder_upload", args=[folder.pk])
        pdf = b"%PDF-1.7\nsynthetic test payload\n%%EOF\n"
        response = self.client.post(url, {"documents":[SimpleUploadedFile("iPhone.jpg", raw),
                                                     SimpleUploadedFile("Özel.pdf", pdf)]}, follow=True)
        self.assertContains(response, "2 evrak kaydedildi.")
        self.assertEqual(2, folder.documents.count())
        record = folder.documents.get(content_type="image/jpeg")
        storage.return_value.upload.assert_any_call(record.storage_path, raw, file_options={
            "content-type": "image/jpeg", "cache-control": "0", "upsert": "false",
        })
        self.assertNotIn("iPhone", record.storage_path)
        storage.return_value.download.return_value = raw
        url = reverse("document_archive_file", args=[record.pk])
        response = self.client.get(url)
        self.assertEqual(response.content, raw)
        self.assertIn("inline", response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual("nosniff", response["X-Content-Type-Options"])
        self.assertNotIn("Location", response)
        storage.return_value.download.return_value = pdf
        url_pdf = reverse("document_archive_file", args=[folder.documents.get(content_type="application/pdf").pk])
        response = self.client.get(url_pdf)
        self.assertIn("attachment", response["Content-Disposition"])

        self.client.force_login(self.mudur)
        manager_home = self.client.get(reverse("document_archive"))
        self.assertContains(manager_home, f'href="{reverse("document_archive")}"')
        storage.return_value.download.return_value = raw
        self.assertEqual(self.client.get(url).content, raw)
        # Preview as regular staff to reach the permission check independently of the shift gate.
        session = self.client.session
        session["moli_preview_user_id"] = self.staff.pk
        session.save()
        denied = self.client.get(url)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.client.get(reverse("document_archive")).status_code, 403)
        self.assertEqual(self.client.post(reverse("document_archive_upload"), {}).status_code, 403)
        self.assertEqual(self.client.post(reverse("document_archive_create_folder"), {"name":"X"}).status_code, 403)
        self.client.logout()
        self.assertRedirects(self.client.get(url), f"/login/?next={url}", fetch_redirect_response=False)

    @patch("core.document_archive_views._private_storage")
    def test_invalid_and_failed_uploads_never_create_records(self, storage):
        response = self.client.post(reverse("document_archive_upload"), {"documents":SimpleUploadedFile("look.jpg", b"<html>")}, follow=True)
        self.assertContains(response, "Dosya okunamadı")
        storage.assert_not_called()
        storage.return_value.upload.side_effect = RuntimeError("mock connection failure")
        response = self.client.post(reverse("document_archive_upload"), {"documents":SimpleUploadedFile("valid.jpg", make_image())}, follow=True)
        self.assertContains(response, "kaydedilemedi")
        self.assertFalse(ArchiveDocument.objects.exists())

    def test_csrf_and_method_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.get(reverse("document_archive_upload")).status_code, 405)
        self.assertEqual(client.post(reverse("document_archive_create_folder"), {"name":"X"}).status_code, 403)


@override_settings(SUPABASE_URL="https://example.supabase.co", SUPABASE_SERVICE_ROLE_KEY="synthetic")
class StorageSetupTest(TestCase):
    @patch("core.document_archive_views.create_client")
    def test_private_bucket_created_on_missing_then_confirmed(self, create):
        setup = create.return_value.storage
        setup.get_bucket.side_effect = [StorageApiError("Bucket not found", "Not Found", 404), SimpleNamespace(public=False)]
        self.assertIs(_private_storage(create=True), setup.from_.return_value)
        self.assertIs(setup.create_bucket.call_args.kwargs["options"]["public"], False)
        setup.from_.assert_called_once_with(BUCKET)

    @patch("core.document_archive_views.create_client")
    def test_never_write_or_read_from_public_bucket(self, create):
        setup = create.return_value.storage
        setup.get_bucket.return_value = SimpleNamespace(public=True)
        with self.assertRaises(RuntimeError):
            _private_storage(create=True)
        setup.from_.assert_not_called()
        setup.create_bucket.assert_not_called()
