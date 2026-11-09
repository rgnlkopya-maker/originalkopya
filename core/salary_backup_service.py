"""Monthly encrypted JSON and readable payroll Excel backup to restricted Drive folder."""
import base64
import io
import json
import os
import secrets
from datetime import date
from decimal import Decimal
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from googleapiclient.http import MediaIoBaseUpload
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from django.contrib.auth import get_user_model
from attendance.models import SalaryProfile, SalaryPeriod, SalaryTransaction, SalaryRate, SalaryPaymentPlan
from core.instrument_drive_oauth import drive_service

FOLDER = "1vlaq3ZzAWomw153BbdPl7L95s-0FX4v8"
MAGIC = b"MOLI-SALARY-BACKUP-1\n"
MODELS = (SalaryProfile, SalaryPeriod, SalaryTransaction, SalaryRate, SalaryPaymentPlan)


def salary_backup():
    key = base64.urlsafe_b64decode(os.environ["MOLI_DB_BACKUP_KEY"] + "===")
    if len(key) != 32:
        raise RuntimeError("Invalid salary backup encryption key")
    data = {"schema": 1, "created_at": timezone.now().isoformat(), "models": {}}
    for model in MODELS:
        fields = [field.attname for field in model._meta.concrete_fields]
        data["models"][model.__name__] = list(model.objects.order_by("pk").values(*fields))
    raw = json.dumps(data, cls=DjangoJSONEncoder, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    # Readable workbook is a report; JSON above retains exact database fields for recovery.
    User = get_user_model()
    people = {u.pk: (u.get_full_name().strip() or u.username) for u in User.objects.all()}
    periods = list(SalaryPeriod.objects.select_related("user").order_by("year", "month", "user_id"))
    transactions = list(SalaryTransaction.objects.select_related("period").order_by("paid_on", "pk"))
    plans = list(SalaryPaymentPlan.objects.order_by("year", "month", "planned_on", "pk"))
    profiles = list(SalaryProfile.objects.order_by("user_id"))
    rates = list(SalaryRate.objects.order_by("user_id", "start_date"))
    paid_by_period = {}
    for tx in transactions:
        if tx.voided_at is None:
            paid_by_period[tx.period_id] = paid_by_period.get(tx.period_id, Decimal("0")) + tx.amount
    wb = Workbook()
    wb.remove(wb.active)
    money_columns = {}
    def sheet(name, headers, rows, monetary=()):
        ws = wb.create_sheet(name)
        ws.append(headers)
        for row in rows:
            ws.append(list(row))
        ws.freeze_panes = "C2" if len(headers) > 3 else "A2"
        ws.auto_filter.ref = ws.dimensions
        ws.sheet_view.showGridLines = False
        ws.row_dimensions[1].height = 28
        for cell in ws[1]:
            cell.fill = PatternFill("solid", fgColor="203B61")
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        for col in range(1, len(headers) + 1):
            letter = ws.cell(1, col).column_letter
            maxlen = max((len(str(ws.cell(row, col).value or "")) for row in range(1, min(ws.max_row, 120) + 1)), default=12)
            ws.column_dimensions[letter].width = min(38, max(16, maxlen + 3))
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if cell.row % 2 == 0:
                    cell.fill = PatternFill("solid", fgColor="F3F7FC")
                if cell.column in monetary:
                    cell.number_format = '#,##0.00 "₺";[Red](#,##0.00 "₺");-'
                elif isinstance(cell.value, date):
                    cell.number_format = "DD.MM.YYYY"
        return ws
    def person(user_id):
        return people.get(user_id, f"Kullanıcı #{user_id}")
    def period_name(year, month):
        return f"{month:02d}.{year}"
    def decimal(value):
        return float(value or 0)
    sheet("Maaş Özeti",
          ["Ad Soyad", "Maaş Dönemi", "Net Maaş", "Ek Ödeme", "Kesinti", "Hak Ediş", "Ödenen", "Kalan", "Durum"],
          [(person(p.user_id), period_name(p.year, p.month), decimal(p.base_net), decimal(p.adjustment), decimal(p.deduction),
            decimal(p.earned), decimal(paid_by_period.get(p.pk, 0)), decimal(p.earned - paid_by_period.get(p.pk, 0)),
            "Kilitli" if p.locked else "Açık") for p in periods], monetary=(3,4,5,6,7,8))
    period_lookup = {p.pk: p for p in periods}
    sheet("Ödemeler ve Avanslar",
          ["Ad Soyad", "Maaş Dönemi", "Ödeme Tarihi", "İşlem Türü", "Ödeme Şekli", "Tutar", "Açıklama", "Durum", "Kaydeden", "İptal Eden", "İptal Tarihi"],
          [(person(period_lookup[t.period_id].user_id), period_name(period_lookup[t.period_id].year, period_lookup[t.period_id].month),
            t.paid_on, t.get_kind_display(), t.get_method_display(), decimal(t.amount), t.note,
            "İptal" if t.voided_at else "Geçerli", person(t.recorded_by_id),
            person(t.voided_by_id) if t.voided_by_id else "", t.voided_at.date() if t.voided_at else None)
           for t in transactions if t.period_id in period_lookup], monetary=(6,))
    sheet("Ödeme Planları",
          ["Ad Soyad", "Maaş Dönemi", "Planlanan Tarih", "İşlem Türü", "Ödeme Şekli", "Planlanan Tutar", "Açıklama", "Durum", "Oluşturan"],
          [(person(p.user_id), period_name(p.year, p.month), p.planned_on, p.get_kind_display(), p.get_method_display(),
            decimal(p.amount), p.note, "Tamamlandı" if p.completed else "Bekliyor", person(p.created_by_id)) for p in plans], monetary=(6,))
    sheet("Maaş Tanımları",
          ["Ad Soyad", "Güncel Net Maaş", "Maaş Listesinde", "Son Güncelleme"],
          [(person(p.user_id), decimal(p.monthly_net), "Evet" if p.visible_in_salary else "Hayır",
            p.updated_at.date() if p.updated_at else None) for p in profiles], monetary=(2,))
    sheet("Maaş Geçmişi",
          ["Ad Soyad", "Net Maaş", "Başlangıç Tarihi", "Bitiş Tarihi", "Tanımlayan"],
          [(person(r.user_id), decimal(r.monthly_net), r.start_date, r.end_date, person(r.created_by_id)) for r in rates], monetary=(2,))
    output = io.BytesIO()
    wb.save(output)
    drive = drive_service()
    folder = drive.files().get(fileId=FOLDER, fields="id,mimeType,trashed,capabilities/canAddChildren").execute()
    if folder.get("trashed") or folder.get("mimeType") != "application/vnd.google-apps.folder" or not folder.get("capabilities", {}).get("canAddChildren", False):
        raise RuntimeError("Salary backup folder is unavailable or read-only")
    stamp = timezone.localtime().strftime("%Y-%m-%d_%H-%M")
    files = []
    for extension, payload in (("json", raw), ("xlsx", output.getvalue())):
        if extension == "json":
            nonce = secrets.token_bytes(12)
            uploaded_bytes = MAGIC + nonce + AESGCM(key).encrypt(nonce, payload, MAGIC)
            name = f"MoliApp-Maas-{stamp}.json.enc"
        else:
            uploaded_bytes = payload
            name = f"MoliApp-Maas-{stamp}.xlsx"
        uploaded = drive.files().create(
            body={"name": name, "parents": [FOLDER], "description": "Encrypted JSON or readable Excel salary backup"},
            media_body=MediaIoBaseUpload(io.BytesIO(uploaded_bytes), mimetype=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if extension == "xlsx" else "application/octet-stream"), resumable=True),
            fields="id,size",
        ).execute()
        remote = drive.files().get(fileId=uploaded["id"], fields="id,size,trashed").execute()
        if remote.get("trashed") or int(remote.get("size", -1)) != len(uploaded_bytes):
            raise RuntimeError("Salary backup upload verification failed: " + extension)
        files.append({"file_id": uploaded["id"], "size": len(uploaded_bytes), "type": extension})
    return {"file_id": files[0]["file_id"], "size": sum(f["size"] for f in files), "records": sum(len(v) for v in data["models"].values()), "files": files}
