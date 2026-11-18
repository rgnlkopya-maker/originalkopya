from io import BytesIO
from django.core.management.base import BaseCommand
from core.models import GalleryMedia
from core.product_gallery_views import _bucket


class Command(BaseCommand):
    help = "Create compact thumbnails for existing gallery photos without altering originals."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        from PIL import Image, ImageOps
        qs = GalleryMedia.objects.filter(thumbnail_path="", content_type__startswith="image/").order_by("pk")
        created = 0
        for media in qs[:max(0, options["limit"])]:
            try:
                raw = _bucket().download(media.storage_path)
                with Image.open(BytesIO(raw)) as source:
                    preview = ImageOps.exif_transpose(source)
                    preview.thumbnail((600, 800))
                    if preview.mode != "RGB":
                        preview = preview.convert("RGB")
                    output = BytesIO()
                    preview.save(output, format="JPEG", quality=78, optimize=True)
                path = media.storage_path + ".thumb.jpg"
                _bucket().upload(path, output.getvalue(), file_options={"content-type": "image/jpeg", "upsert": "true"})
                GalleryMedia.objects.filter(pk=media.pk, thumbnail_path="").update(thumbnail_path=path)
                created += 1
            except Exception as exc:
                self.stderr.write(f"Media {media.pk}: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Created {created} gallery thumbnails."))
