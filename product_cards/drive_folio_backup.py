import io
import json
import logging
import os
import re
import threading
from decimal import Decimal

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from .models import ShowroomDraft

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]
ROOT_FOLDER_ENV = "MOLIAPP_FOLIO_DRIVE_FOLDER_ID"
SERVICE_ACCOUNT_ENV = "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON"


def _money(value):
    value = Decimal(str(value or 0))
    raw = f"{value:,.2f}"
    return raw.replace(",", "X").replace(".", ",").replace("X", ".") + " TL"


def _safe_name(value):
    value = re.sub(r"[^0-9A-Za-zÇĞİÖŞÜçğıöşü_-]+", "_", str(value or "").strip())
    return value.strip("_") or "MUSTERI"


def _drive_service():
    raw = os.environ.get(SERVICE_ACCOUNT_ENV, "").strip()
    if not raw:
        raise RuntimeError(f"{SERVICE_ACCOUNT_ENV} tanimli degil")
    info = json.loads(raw)
    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _escape(value):
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _pdf_bytes(draft):
    draft = (
        ShowroomDraft.objects.select_related("customer")
        .prefetch_related("items__product_card__urun", "payments")
        .get(pk=draft.pk)
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"Siparis Foyu #{draft.id}",
        author="Moli Tekstil",
    )

    body = ParagraphStyle("body", fontName="Helvetica", fontSize=8, leading=10)
    small = ParagraphStyle("small", fontName="Helvetica", fontSize=7, leading=9)
    title_style = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=17, leading=19)
    right = ParagraphStyle("right", parent=body, alignment=TA_RIGHT)
    right_small = ParagraphStyle("right_small", parent=small, alignment=TA_RIGHT)

    status_label = {
        "PENDING": "Taslak",
        "APPROVED": "Onaylanan",
        "TRANSFERRED": "Siparise Aktarildi",
    }.get(draft.status, draft.status)

    story = []
    title = Table(
        [[
            Paragraph("<b>MOLI</b>", title_style),
            Paragraph(
                f"<b>SIPARIS FOYU</b><br/><font size='8'>Foy No: #{draft.id}</font>",
                right,
            ),
        ]],
        colWidths=[92 * mm, 92 * mm],
    )
    title.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 1.5, colors.HexColor("#27324a")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([title, Spacer(1, 5 * mm)])

    customer = draft.customer.ad if draft.customer else "Musteri secilmedi"
    local_dt = timezone.localtime(draft.updated_at).strftime("%d.%m.%Y %H:%M")
    meta = Table(
        [[
            Paragraph(f"<b>Musteri</b><br/>{_escape(customer)}", body),
            Paragraph(f"<b>Siparisi Alan</b><br/>{_escape(draft.order_taken_by or '-')}", body),
            Paragraph(f"<b>Durum</b><br/>{_escape(status_label)}", body),
            Paragraph(f"<b>Tarih</b><br/>{local_dt}", body),
        ]],
        colWidths=[75 * mm, 39 * mm, 35 * mm, 35 * mm],
    )
    meta.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dfe4eb")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dfe4eb")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f8fa")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([meta, Spacer(1, 4 * mm)])

    groups = {}
    for item in draft.items.all().order_by("created_at", "id"):
        key = (item.product_card.urun.kod, item.unit_price)
        groups.setdefault(key, []).append(item)

    subtotal = Decimal("0")
    for (code, unit_price), rows in groups.items():
        row_data = [[
            Paragraph("<b>Renk</b>", small),
            Paragraph("<b>Beden</b>", small),
            Paragraph("<b>Adet</b>", small),
            Paragraph("<b>Aciklama</b>", small),
            Paragraph("<b>Birim Fiyat</b>", small),
            Paragraph("<b>Satir Toplami</b>", small),
        ]]
        item_total = Decimal("0")
        for row in rows:
            line_total = Decimal(row.quantity) * row.unit_price
            item_total += line_total
            subtotal += line_total
            row_data.append([
                Paragraph(_escape(row.color or "-"), small),
                Paragraph(_escape(row.size or "-"), small),
                str(row.quantity),
                Paragraph(_escape(row.description or "-"), small),
                _money(row.unit_price),
                _money(line_total),
            ])

        product_head = Table(
            [[
                Paragraph(f"<b>{_escape(code)}</b>", body),
                Paragraph(
                    f"Birim Fiyat: {_money(unit_price)} &nbsp; | &nbsp; Urun Toplami: {_money(item_total)}",
                    right_small,
                ),
            ]],
            colWidths=[70 * mm, 114 * mm],
        )
        product_head.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3f5f8")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dce1e8")),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        product_table = Table(
            row_data,
            colWidths=[26 * mm, 19 * mm, 13 * mm, 43 * mm, 40 * mm, 43 * mm],
            repeatRows=1,
        )
        product_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dce1e8")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fafbfc")),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (2, 1), (2, -1), "CENTER"),
            ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        story.extend([KeepTogether([product_head, product_table]), Spacer(1, 3 * mm)])

    payments = list(draft.payments.all().order_by("due_date", "payment_date", "id"))
    collected = sum(
        (p.amount for p in payments if p.entry_type == "COLLECTION"),
        Decimal("0"),
    )
    if payments:
        payment_rows = [[
            "Tur", "Sekil", "Tutar", "Tahsilat", "Soz / Vade", "Not"
        ]]
        for p in payments:
            payment_rows.append([
                p.get_entry_type_display(),
                p.get_method_display(),
                _money(p.amount),
                p.payment_date.strftime("%d.%m.%Y") if p.payment_date else "-",
                p.due_date.strftime("%d.%m.%Y") if p.due_date else "-",
                Paragraph(_escape(p.note or "-"), small),
            ])
        ptable = Table(
            payment_rows,
            colWidths=[28 * mm, 28 * mm, 32 * mm, 30 * mm, 30 * mm, 36 * mm],
            repeatRows=1,
        )
        ptable.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dce1e8")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fafbfc")),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.extend([
            Paragraph("<b>TAHSILAT / ODEME PLANI</b>", body),
            Spacer(1, 2 * mm),
            ptable,
            Spacer(1, 4 * mm),
        ])

    discount = (
        subtotal * draft.discount_rate / Decimal("100")
        if draft.discount_rate and draft.discount_rate > 0
        else (draft.overall_discount_amount or Decimal("0"))
    )
    discount = min(subtotal, max(Decimal("0"), discount))
    taxable = max(Decimal("0"), subtotal - discount)
    vat_rate = max(Decimal("0"), min(Decimal("100"), draft.vat_rate or Decimal("0")))
    vat = taxable * vat_rate / Decimal("100")
    folio_total = taxable + vat
    previous = max(Decimal("0"), draft.previous_balance or Decimal("0"))
    grand_total = folio_total + previous
    remaining = max(Decimal("0"), grand_total - collected)

    totals = Table(
        [
            ["Ara Toplam", _money(subtotal)],
            ["Indirim", "-" + _money(discount)],
            [f"KDV (%{vat_rate})", _money(vat)],
            ["Foy Toplami", _money(folio_total)],
            ["Eski Bakiye", _money(previous)],
            ["GENEL TOPLAM", _money(grand_total)],
            ["Tahsil Edilen", "-" + _money(collected)],
            ["KALAN", _money(remaining)],
        ],
        colWidths=[45 * mm, 45 * mm],
        hAlign="RIGHT",
    )
    totals.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 5), (-1, 5), "Helvetica-Bold"),
        ("FONTNAME", (0, 7), (-1, 7), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, colors.HexColor("#27324a")),
        ("LINEABOVE", (0, 5), (-1, 5), 0.5, colors.HexColor("#ccd2dc")),
        ("LINEABOVE", (0, 7), (-1, 7), 0.5, colors.HexColor("#ccd2dc")),
        ("PADDING", (0, 0), (-1, -1), 5),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    story.extend([
        totals,
        Spacer(1, 5 * mm),
        Paragraph(
            f"Moli Tekstil &nbsp;&nbsp;&nbsp; Foy #{draft.id} - {_escape(status_label)}",
            small,
        ),
    ])

    doc.build(story)
    buf.seek(0)
    return buf


def _year_folder(service, root_folder_id, year):
    escaped = str(year).replace("'", "\\'")
    query = (
        f"'{root_folder_id}' in parents and name='{escaped}' "
        "and mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    found = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id,name)",
        pageSize=10,
    ).execute().get("files", [])
    if found:
        return found[0]["id"]

    created = service.files().create(
        body={
            "name": str(year),
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [root_folder_id],
        },
        fields="id",
    ).execute()
    return created["id"]


def sync_folio_to_drive(draft_id):
    root_folder_id = os.environ.get(ROOT_FOLDER_ENV, "").strip()
    if not root_folder_id:
        raise RuntimeError(f"{ROOT_FOLDER_ENV} tanimli degil")

    draft = (
        ShowroomDraft.objects.select_related("customer")
        .prefetch_related("items__product_card__urun", "payments")
        .get(pk=draft_id)
    )
    if draft.status not in {"APPROVED", "TRANSFERRED"}:
        return False

    service = _drive_service()
    year = timezone.localtime(draft.updated_at).year
    folder_id = _year_folder(service, root_folder_id, year)
    customer = draft.customer.ad if draft.customer else "MUSTERI"
    filename = f"FOY-{draft.id}_{_safe_name(customer)}.pdf"

    q_name = filename.replace("'", "\\'")
    query = (
        f"'{folder_id}' in parents and name='{q_name}' "
        "and mimeType='application/pdf' and trashed=false"
    )
    existing = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id,name)",
        pageSize=10,
    ).execute().get("files", [])

    pdf = _pdf_bytes(draft)
    media = MediaIoBaseUpload(pdf, mimetype="application/pdf", resumable=False)

    if existing:
        service.files().update(
            fileId=existing[0]["id"],
            media_body=media,
            fields="id,name,modifiedTime",
        ).execute()
    else:
        service.files().create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media,
            fields="id,name,modifiedTime",
        ).execute()
    return True


def _safe_sync(draft_id):
    try:
        sync_folio_to_drive(draft_id)
    except Exception:
        logger.exception("Siparis foyunun Drive yedegi alinamadi: draft_id=%s", draft_id)


def queue_folio_drive_sync(draft_id):
    if not os.environ.get(SERVICE_ACCOUNT_ENV):
        logger.warning(
            "Drive anlik yedekleme pasif: %s tanimli degil (draft_id=%s)",
            SERVICE_ACCOUNT_ENV,
            draft_id,
        )
        return
    thread = threading.Thread(
        target=_safe_sync,
        args=(draft_id,),
        name=f"folio-drive-sync-{draft_id}",
        daemon=True,
    )
    thread.start()
