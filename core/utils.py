# core/utils.py
import qrcode
import io
from supabase import create_client
from django.conf import settings

def ensure_order_qr(order):
    """
    Order için QR yoksa üretir ve Supabase'e yükler.
    Sonrasında order.qr_code_url alanını set eder.
    """

    if order.qr_code_url:
        return  # ✅ zaten var

    qr_data = f"https://originalkopya.onrender.com/order/{order.id}/"
    qr = qrcode.make(qr_data)

    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)

    filename = f"qr_{order.id}.png"

    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    bucket = supabase.storage.from_(settings.SUPABASE_BUCKET_NAME)

    # ✅ UPLOAD (upsert parametresini STRING veriyoruz ki header bool hatası olmasın)
    bucket.upload(
        filename,
        buffer.getvalue(),
        file_options={"content-type": "image/png"},
        upsert="true"
    )

    # ✅ Public URL al
    public_url = bucket.get_public_url(filename)

    order.qr_code_url = public_url
    order.save(update_fields=["qr_code_url"])
