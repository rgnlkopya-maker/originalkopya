import os
import io
import qrcode
from supabase import create_client
from django.conf import settings


def get_supabase():
    """
    Supabase client üretir.
    Render'da env var ise onu okur, settings'te varsa onu okur.
    Local'de env yoksa None döner (patlamasın).
    """
    url = getattr(settings, "SUPABASE_URL", None) or os.getenv("SUPABASE_URL")
    key = (
        getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
    )

    if not url or not key:
        return None

    return create_client(url, key)


def ensure_order_qr(order):
    """
    Siparişin QR'ı yoksa:
    - üret
    - Supabase'a yükle
    - public URL'i DB'ye kaydet
    """

    # 1) zaten varsa dokunma
    if order.qr_code_url:
        return order.qr_code_url

    supabase = get_supabase()
    if not supabase:
        print("❌ Supabase env yok / client üretilemedi")
        return None

    # 2) QR içeriği: sipariş detay URL
    base_url = getattr(settings, "BASE_URL", "").rstrip("/")
    if not base_url:
        base_url = "https://originalkopya.onrender.com"

    qr_data = f"{base_url}/orders/{order.id}/"

    # 3) QR üret
    qr = qrcode.make(qr_data)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)

    bucket = "order-qr"
    filename = f"orders/order_{order.id}.png"

    try:
        # 4) Upload (upsert True => asla patlamasın)
        supabase.storage.from_(bucket).upload(
            filename,
            buffer.getvalue(),
            file_options={
                "content-type": "image/png",
                "upsert": True
            }
        )

        # 5) Public URL al (client sürüm farklılıklarını destekle)
        public_url = supabase.storage.from_(bucket).get_public_url(filename)
        if isinstance(public_url, dict):
            public_url = public_url.get("data", {}).get("publicUrl") or public_url.get("data", {}).get("publicURL")

        if not public_url:
            print("❌ Public URL alınamadı")
            return None

        # 6) DB’ye yaz (signal recursion olmasın diye update önerilir)
        type(order).objects.filter(pk=order.pk).update(qr_code_url=public_url)

        return public_url

    except Exception as e:
        print("❌ QR upload hatası:", e)
        return None
