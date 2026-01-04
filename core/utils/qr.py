import qrcode
import io
from supabase import create_client
from django.conf import settings

def ensure_order_qr(order):
    if order.qr_code_url:
        return

    qr_data = f"https://originalkopya.onrender.com/order/{order.id}/"
    qr = qrcode.make(qr_data)

    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)

    filename = f"orders/qr_{order.id}.png"

    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    bucket = supabase.storage.from_(settings.SUPABASE_BUCKET_NAME)  # burada order-qr olacak

    bucket.upload(
        filename,
        buffer.getvalue(),
        file_options={
            "content-type": "image/png",
            "upsert": "true"
        }
    )

    public_url = bucket.get_public_url(filename)

    order.qr_code_url = public_url
    order.save(update_fields=["qr_code_url"])
