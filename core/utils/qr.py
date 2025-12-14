import io
import qrcode
from django.conf import settings
from .supabase import supabase


def ensure_order_qr(order):
    """
    Siparişin QR'ı yoksa:
    - üret
    - Supabase'a yükle
    - public URL'i DB'ye kaydet
    Varsa: dokunma
    """

    # ZATEN VARSA → ÇIK
    if order.qr_code_url:
        return order.qr_code_url

    qr_data = f"{settings.BASE_URL}/order/{order.id}/"

    qr = qrcode.make(qr_data)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)

    filename = f"order_{order.id}.png"

    # Supabase upload (overwrite YOK)
    supabase.storage.from_("order-qr").upload(
        filename,
        buffer.getvalue(),
        file_options={
            "content-type": "image/png",
            "upsert": False
        }
    )

    public_url = supabase.storage.from_("order-qr").get_public_url(filename)

    order.qr_code_url = public_url
    order.save(update_fields=["qr_code_url"])

    return public_url
