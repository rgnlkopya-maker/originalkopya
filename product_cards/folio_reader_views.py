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
PROMPT = """You are a highly precise visual transcriber of HANDWRITTEN TURKISH TEXTILE ORDER TABLES.
Return ONLY JSON, never guess. A wrong product/size/quantity/price costs real production money.
Read the form like a spreadsheet with a fixed header row, not as running text.
First locate the table's physical columns. The printed size headers are 38 | 40 | 42 | 44 | 46 | 48.
A tick mark must be assigned to the size column directly ABOVE IT. Most tick marks may be in 40, not 38.
For each handwritten product row, read LEFT TO RIGHT: KOD, RENK, checked SIZE columns, ADET, FIYATI, TUTARI.
Carry down a repeated product code only when it is visibly the SAME product row; otherwise do not invent.
Transcribe every physical row including repeated codes, and preserve its order. Read all the way down to the totals.
Do not confuse notes such as "Biritli" or "Tesettür" (often on a separate line) with new products or colors;
attach to the preceding or following appropriate product ONLY when visually clear; otherwise add an uncertainty.
If two size columns are ticked on a row, return two item objects, with the respective quantities if visible.
If quantity total is 2 and there are two checked sizes, use quantity 1 per size ONLY if clearly consistent.
Money uses Turkish thousands separators: 21.000 = 21000, 26.500 = 26500; never generate amounts like 20664 from 21000.
Read the totals box separately:
"Adet" bottom number is written_total_qty, "Tutar" is written_subtotal.
A line marked "%40" is 40 percent, NOT 15.6, and never infer a percentage from the amount alone.
If discount amount is written, transcribe it as written_discount_amount for comparison.
The bottom "Toplam" after discount is written_folio_total.
Treat written subtotal and discount and total as evidence to CHECK, not as a target to force-fit prices.
NEVER alter a unit price to make the written subtotal agree. NEVER invent currency, VAT, dates or customer.
If a field is ambiguous, use null and add a specific uncertainty in Turkish with its physical row number.
Return JSON with exact keys:
customer (string|null), order_taken_by (string|null),
currency ("TRY"|"USD"|"EUR"|"GBP"|null), order_type ("SERI"|"TEKLI"|"STOK"|"KONSINYE"|"OZEL"|null),
items (array of {row_number:integer,product_code:string|null,color:string|null,size:string|null,
quantity:integer|null,unit_price:number|null,description:string|null,written_line_total:number|null}),
pricing_operations (array of {type:"DISCOUNT"|"VAT",mode:"PERCENT"|"AMOUNT",value:number}),
written_total_qty (integer|null), written_subtotal (number|null),
written_discount_amount (number|null), written_folio_total (number|null),
written_grand_total (number|null), previous_balance (number|null),
delivery_date ("YYYY-MM-DD"|null), notes (string|null), unclear (array of Turkish strings).
For a row with two sizes use repeated row_number. Keep every product row; if illegible use null, do not OMIT it.
Checks: sum item quantities should equal written_total_qty if present;
sum quantity * unit_price should match written_subtotal when every price is readable;
discount percent and discount amount should be mutually consistent.
Even if these checks fail, do NOT silently fix amounts. Add the specific discrepancy to unclear.
Output JSON only."""


def _image_data(upload):
    """Make a focused image of the written content, avoiding large empty paper margins."""
    if upload.size < 50 or upload.size > MAX_BYTES:
        raise ValueError("Fotoğraf 10 MB sınırında ve boş olmayan bir dosya olmalı.")
    try:
        with Image.open(upload) as original:
            if original.format not in ("JPEG", "PNG", "WEBP", "HEIF", "HEIC", "MPO", "TIFF"):
                raise ValueError("Lütfen JPEG, PNG, WEBP veya HEIC biçiminde fotoğraf yükleyin.")
            original.seek(0)
            image = ImageOps.exif_transpose(original).convert("RGB")
            # Some photos have a very large white bottom area that makes the table tiny.
            # Crop only if the content bounding box is clear and the savings are meaningful.
            if image.width >= 250 and image.height >= 250:
                gray = image.convert("L")
                ink = gray.point(lambda x: 255 if x < 205 else 0)
                bbox = ink.getbbox()
                if bbox:
                    margin = max(14, int(min(image.size) * .025))
                    left, top, right, bottom = bbox
                    bbox = (max(0, left - margin), max(0, top - margin),
                            min(image.width, right + margin), min(image.height, bottom + margin))
                    if (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) < image.width * image.height * .82:
                        image = image.crop(bbox)
            # Provide the full page and two overlapping close-ups in a SINGLE API request.
            # Each crop retains table headers/row positions; the full page anchors totals.
            views = [image]
            if image.height > 500:
                height = image.height
                views.extend([
                    image.crop((0, 0, image.width, int(height * .65))),
                    image.crop((0, int(height * .35), image.width, height)),
                ])
            urls = []
            for view in views:
                view.thumbnail((2800, 2800))
                buffer = io.BytesIO()
                view.save(buffer, "JPEG", quality=92, optimize=True)
                urls.append("data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"))
            return urls
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
        image_urls = _image_data(upload)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    requested_model = request.POST.get("model", "gpt-4.1").strip()
    allowed_models = {"gpt-4.1", "gpt-6.1-sol", "gpt-6-astra"}
    if requested_model not in allowed_models:
        return JsonResponse({"ok": False, "error": "Desteklenmeyen okuma modeli."}, status=400)
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return JsonResponse({"ok": False, "error": "El yazısı okuma için OPENAI_API_KEY henüz Render ortamında tanımlı değil."}, status=503)
    try:
        payload = {
            "model": requested_model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "These are three views of the SAME form: full page, upper crop and lower crop. Do not double-count overlapping rows. Extract all rows and totals."},
                    *[{"type": "image_url", "image_url": {"url": url, "detail": "high"}} for url in image_urls],
                ]},
            ],
        }
        if requested_model == "gpt-4.1":
            payload["temperature"] = 0
            payload["max_completion_tokens"] = 5000
        else:
            # Reasoning models may reject temperature; use completion token budget.
            payload["max_completion_tokens"] = 5500
            payload["reasoning_effort"] = "low"
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            json=payload,
            timeout=(5, 22),
        )
        if response.status_code == 400:
            logger.warning("Folio model rejected request: model=%s", requested_model)
            return JsonResponse({"ok": False, "error": "Seçilen model okuma isteğini kabul etmedi. Başka bir model seçin; mevcut föy değişmedi."}, status=503)
        if response.status_code == 429:
            try:
                api_error = response.json().get("error") or {}
                code = str(api_error.get("code") or api_error.get("type") or "")
            except (ValueError, AttributeError):
                code = ""
            logger.warning("Folio vision API returned 429; category=%s", code[:80])
            if code in ("insufficient_quota", "billing_hard_limit_reached"):
                message = "El yazısı okuma servisi: API bakiyesi veya kullanım kotası yetersiz. API hesabının ödeme ve kullanım limitlerini kontrol edin."
            else:
                message = "El yazısı okuma servisi hız sınırına ulaştı (429). Bir süre sonra tekrar deneyin; sorun sürerse API kullanım limitlerini kontrol edin."
            return JsonResponse({"ok": False, "error": message, "api_error_code": code[:80]}, status=503)
        if response.status_code == 401:
            return JsonResponse({"ok": False, "error": "El yazısı okuma API anahtarı geçersiz. Render API ayarlarını kontrol edin."}, status=503)
        if response.status_code == 403:
            return JsonResponse({"ok": False, "error": "El yazısı okuma servisine erişim engellendi. API hesabı veya model erişimini kontrol edin."}, status=503)
        response.raise_for_status()
        result = response.json()
        parsed = json.loads(result["choices"][0]["message"]["content"])
        if not isinstance(parsed, dict) or not isinstance(parsed.get("items"), list):
            raise ValueError("Beklenen alanlar okuma yanıtında bulunamadı.")
        parsed["items"] = parsed["items"][:200]
        usage = result.get("usage") or {}
        return JsonResponse({"ok": True, "data": parsed, "model": requested_model,
                             "usage": {"input_tokens": usage.get("prompt_tokens"),
                                       "output_tokens": usage.get("completion_tokens"),
                                       "total_tokens": usage.get("total_tokens")}})
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        logger.exception("Handwritten folio reading failed")
        return JsonResponse({"ok": False, "error": "Fotoğraf okunamadı veya okuma servisi yanıt vermedi. Tekrar deneyin."}, status=503)
