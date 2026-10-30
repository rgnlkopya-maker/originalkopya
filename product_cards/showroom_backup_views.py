"""Manual incremental Google Drive archive for saved order folios."""
import hashlib
import io
import json
import logging
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from core.instrument_backup_views import _folder, _existing_file, _upload
from core.instrument_drive_oauth import drive_service, connected
from .models import ShowroomDraft
from .showroom_photo_views import storage
from .showroom_views import _effective_serialized_items, _draft_summary

logger = logging.getLogger(__name__)
ROOT_ID = "1Ao-9uebg2eVb9hb1tCf5cwEPGLUE0MYf"

def _safe_name(value):
    cleaned = re.sub(r"[^\\w -]", "", str(value or ""), flags=re.UNICODE)
    return re.sub(r"\\s+", " ", cleaned).strip()[:65] or "Musteri Yok"

def check_folio_root(drive):
    root = drive.files().get(fileId=ROOT_ID, fields="id,name,mimeType,capabilities(canAddChildren)", supportsAllDrives=True).execute()
    if root.get("mimeType") != "application/vnd.google-apps.folder" or not root.get("capabilities", {}).get("canAddChildren", False):
        raise PermissionError("Sipariş Föyleri Drive klasörüne erişim veya yazma izni yok.")



def _font():
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        pdfmetrics.getFont("FolioArchiveFont")
    except KeyError:
        try:
            pdfmetrics.registerFont(TTFont("FolioArchiveFont", path))
        except Exception:
            return "Helvetica"
    return "FolioArchiveFont"


def _pdf(data):
    """Readable folio archive PDF. Original 'Yazdır' screen remains unchanged."""
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=A4)
    font = _font()
    width, height = A4
    y = height - 45

    def line(value, size=9):
        nonlocal y
        value = str(value or "").replace("\n", " ")
        parts = simpleSplit(value, font, size, width - 85) or [""]
        for part in parts:
            if y < 57:
                pdf.showPage()
                y = height - 45
            pdf.setFont(font, size)
            pdf.drawString(43, y, part)
            y -= size + 6

    line(f"SIPARIS FOYU #{data['id']}", 16)
    line(f"Musteri: {data['customer']} | Durum: {data['status']} | Tarih: {data['created_at']}")
    line(f"Para birimi: {data['currency']} | Siparis tipi: {data['order_type']}")
    line("-------------------------------------------------------")
    for idx, item in enumerate(data["items"], 1):
        line(f"{idx}. {item.get('urun_kodu','')} | Birim fiyat: {item.get('anlasilan_fiyat','')}", 11)
        for row in item.get("satirlar", []):
            line(f"  Renk: {row.get('renk','')} | Beden: {', '.join(str(v) for v in (row.get('bedenler') or []))} | Adet: {row.get('adet','')} | Not: {row.get('aciklama','')}")
    line("-------------------------------------------------------")
    line("Veri arsivi - MoliApp yazdirma ekranindan bagimsiz PDF.")
    pdf.save()
    return stream.getvalue()


def _snapshot(draft):
    data = {
        "id": draft.pk,
        "customer": draft.customer.ad if draft.customer else "",
        "customer_id": draft.customer_id,
        "status": draft.status,
        "currency": draft.currency,
        "order_type": draft.order_type,
        "order_taken_by": draft.order_taken_by,
        "created_at": draft.created_at.isoformat(),
        "updated_at": draft.updated_at.isoformat(),
        "vat_rate": str(draft.vat_rate),
        "discount_rate": str(draft.discount_rate),
        "previous_balance": str(draft.previous_balance),
        "pricing_operations": draft.pricing_operations,
        "items": _effective_serialized_items(draft),
        "payments": [
            {key: str(getattr(p, key, "") or "") for key in
             ("id", "entry_type", "amount", "currency", "payment_date", "due_date", "note")}
            for p in draft.payments.all()
        ],
        "photos": [
            {"id": p.pk, "file": p.storage_path.rsplit("/", 1)[-1], "original_name": p.original_name}
            for p in draft.source_photos.all()
        ],
    }
    return data


@login_required
@require_POST
def backup(request):
    if not (request.user.is_superuser or request.user.groups.filter(name__in=("patron", "mudur")).exists()):
        return HttpResponseForbidden("Yetkiniz yok.")
    if not connected():
        messages.error(request, "Google Drive hesabini once baglayin.", extra_tags="folio_backup")
        return redirect("showroom_drafts_page")
    incremental = request.POST.get("incremental") == "1"
    try:
        draft_id = int(request.POST.get("draft_id") or 0) if incremental else 0
        drive = drive_service()
        check_folio_root(drive)
        photo_root = _folder(drive, ROOT_ID, "Orijinal Föyler")
        data_root = _folder(drive, ROOT_ID, "Veri Yedekleri")
        pdf_root = _folder(drive, ROOT_ID, "MoliApp Föyleri")
        base_drafts = ShowroomDraft.objects.filter(status__in=["PENDING", "APPROVED", "TRANSFERRED"])
        if incremental:
            base_drafts = base_drafts.filter(pk__gt=draft_id)[:1]
        drafts = list(
            base_drafts
            .select_related("customer")
            .prefetch_related("items__product_card__urun", "payments", "source_photos")
            .order_by("pk")
        )
        uploaded_folios = 0
        uploaded_photos = 0
        for draft in drafts:
            label = f"Foy-{draft.pk} - {_safe_name(draft.customer.ad if draft.customer else None)}"
            archive = _snapshot(draft)
            contents = json.dumps(archive, ensure_ascii=False, sort_keys=True, indent=2, default=str).encode("utf-8")
            # Hash only source content, not the backup run timestamp.
            # Store versions by digest; same input is never uploaded twice.
            for extension, binary, mime in [
                ("json", contents, "application/json"),
                ("pdf", _pdf(archive), "application/pdf"),
            ]:
                digest = hashlib.sha256(binary).hexdigest()[:16]
                name = f"{label} - {digest}.{extension}"
                target = data_root if extension == "json" else pdf_root
                if not _existing_file(drive, target, name):
                    _upload(drive, target, name, binary, mime)
                    uploaded_folios += 1
            if archive["photos"]:
                photo_folder = _folder(drive, photo_root, label)
                for photo in draft.source_photos.all():
                    name = f"Foy-{draft.pk} - Foto-{photo.pk} - " + photo.storage_path.rsplit("/", 1)[-1]
                    existing = _existing_file(drive, photo_folder, name)
                    if existing and int(existing.get("size") or 0) > 0:
                        continue
                    if existing:
                        raise RuntimeError("Bos Drive fotografi: " + name)
                    binary = storage().download(photo.storage_path)
                    if not binary:
                        raise RuntimeError("Fotograf okunamadi: " + name)
                    ext = name.lower().rsplit(".", 1)[-1]
                    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "application/octet-stream")
                    _upload(drive, photo_folder, name, binary, mime)
                    uploaded_photos += 1
        if incremental:
            next_id = drafts[-1].pk if drafts else draft_id
            remaining = ShowroomDraft.objects.filter(status__in=["PENDING", "APPROVED", "TRANSFERRED"], pk__gt=next_id).exists()
            return JsonResponse({"ok": True, "done": not remaining, "next_id": next_id,
                                 "folios": len(drafts), "files": uploaded_folios, "photos": uploaded_photos})
        messages.success(request, f"Föy yedeği tamamlandı: {len(drafts)} föy tarandı, {uploaded_folios} yeni/değişen PDF veya veri dosyası, {uploaded_photos} yeni fotoğraf yüklendi.", extra_tags="folio_backup")
    except Exception:
        logger.exception("Showroom folio backup failed")
        if incremental:
            return JsonResponse({"ok": False, "message": "Bu föy yedeklenemedi. Mevcut Drive dosyaları korundu."}, status=500)
        messages.error(request, "Föy yedeklemesi tamamlanamadı. Mevcut Drive dosyaları korunuyor; yeniden deneyebilirsiniz.", extra_tags="folio_backup")
    return redirect("showroom_drafts_page")
