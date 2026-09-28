from io import BytesIO

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}


def validate_image_upload(uploaded_file):
    """Validate image bytes, not the client supplied filename or MIME type."""
    if not uploaded_file:
        raise ValidationError("Görsel dosyası bulunamadı.")
    if uploaded_file.size > MAX_IMAGE_BYTES:
        raise ValidationError("Görsel en fazla 10 MB olabilir.")

    try:
        uploaded_file.seek(0)
        data = uploaded_file.read()
        with Image.open(BytesIO(data)) as image:
            image.verify()
            image_format = (image.format or "").upper()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("Dosya geçerli bir görsel değil.")
    finally:
        uploaded_file.seek(0)

    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError("Yalnızca JPEG, PNG veya WEBP görseller yüklenebilir.")

    extension, content_type = ALLOWED_IMAGE_FORMATS[image_format]
    return extension, content_type
