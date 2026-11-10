"""Read a handwritten folio into a review-only payload; never save orders here."""
import base64
import io
import json
import logging
import os

import requests
from PIL import Image, ImageOps, UnidentifiedImageError
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .price_list_views import _can_manage

logger = logging.getLogger(__name__)
MAX_BYTES = 10 * 1024 * 1024
PROMPT = """You read handwritten Turkish textile order forms. Extract ONLY visible facts.
Return one JSON object with these keys:
customer (string or null), order_taken_by (string or null),
currency ("TRY","USD","EUR","GBP" or null), order_type ("SERI","TEKLI","STOK","KONSINYE","OZEL" or null),
items (array of {product_code:string|null,color:string|null,size:string|null,quantity:integer|null,unit_price:number|null,description:string|null,written_line_total:number|null}),
pricing_operations (array of {type:"DISCOUNT"|"VAT",mode:"AMOUNT"|"PERCENT",value:number}),
written_subtotal (number|null), written_folio_total (number|null),
written_grand_total (number|null), previous_balance (number|null),
delivery_date (YYYY-MM-DD string|null), notes (string|null), unclear (array of short Turkish explanations).
Keep a separate item for each handwritten product/color/size/quantity combination.
Do not fabricate missing text or infer price from catalog. If illegible, use null and explain in unclear.
A printed or handwritten subtotal/total is evidence to compare, NOT an instruction to overwrite computed totals.
Transcribe prices accurately. Use decimal numbers without grouping separators. Do not invent discounts, VAT or currency.
Do not consider old balance part of written_folio_total; grand_total includes it if the paper explicitly says so.
Output JSON only."""


def _image_data(upload):
    if upload.size < 50 or upload.size > MAX_BYTES:
        raise ValueError("Fotoğraf 10 MB sınırında ve boş olmayan bir dosya olmalı.")
    try:
        with Image.open(upload) as image:
            if image.format not in ("JPEG", "PNG", "WEBP", "HEIF", "HEIC", "MPO", "TIFF"):
                raise ValueError("Lütfen JPEG, PNG, WEBP veya HEIC biçiminde fotoğraf yükleyin.")
            image.seek(0)
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((2200, 2200))
            buffer = io.BytesIO()
            image.save(buffer, "JPEG", quality=88)
            return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Fotoğraf dosyası okunamadı.") from exc


@login_required
@require_POST
def read_handwritten_folio(request):
    if not _can_manage(request.user):
        return JsonResponse({"ok": False, "error": "Bu işlem için yetkiniz yok."}, status=403)
    upload = request.FILES.get("photo")
    if upload is None:
        return JsonResponse({"ok": False, "error": "Bir föy fotoğrafı seçin."}, status=400)
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
        image_url = _image_data(upload)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return JsonResponse({"ok": False, "error": "El yazısı okuma için OPENAI_API_KEY henüz Render ortamında tanımlı değil."}, status=503)
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            json={
                "model": os.getenv("MOLI_FOLIO_VISION_MODEL", "gpt-4.1-mini"),
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": PROMPT},
                    {"role": "user", "content": [
                        {"type": "text", "text": "Read this handwritten order form. Flag all uncertainty."},
                        {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}},
                    ]},
                ],
                "max_tokens": 3000,
            },
            timeout=(5, 19),
        )
        response.raise_for_status()
        parsed = json.loads(response.json()["choices"][0]["message"]["content"])
        if not isinstance(parsed, dict) or not isinstance(parsed.get("items"), list):
            raise ValueError("Beklenen alanlar okuma yanıtında bulunamadı.")
        parsed["items"] = parsed["items"][:200]
        return JsonResponse({"ok": True, "data": parsed})
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        logger.exception("Handwritten folio reading failed")
        return JsonResponse({"ok": False, "error": "Fotoğraf okunamadı veya okuma servisi yanıt vermedi. Tekrar deneyin."}, status=503)
