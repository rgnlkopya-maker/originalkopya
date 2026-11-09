"""Encrypted monthly salary archive to private Drive folder. No plaintext salary uploads."""
import base64
import io
import json
import os
import secrets
from datetime import date
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from googleapiclient.http import MediaIoBaseUpload
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
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

    wb = Workbook()
    wb.remove(wb.active)
    names = {"SalaryProfile": "Maas Tanimlari", "SalaryPeriod": "Maas Donemleri", "SalaryTransaction": "Odemeler ve Avanslar", "SalaryRate": "Maas Gecmisi", "SalaryPaymentPlan": "Odeme Planlari"}
    for model in MODELS:
        ws = wb.create_sheet(names[model.__name__])
        fields = [field.attname for field in model._meta.concrete_fields]
        ws.append(fields)
        for record in data["models"][model.__name__]:
            ws.append([str(record.get(f)) if record.get(f) is not None else "" for f in fields])
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        ws.sheet_view.showGridLines = False
        for cell in ws[1]:
            cell.fill = PatternFill("solid", fgColor="203B61")
            cell.font = Font(color="FFFFFF", bold=True)
        for column in ws.columns:
            ws.column_dimensions[column[0].column_letter].width = min(34, max(14, max(len(str(c.value or "")) for c in list(column)[:100]) + 2))
    output = io.BytesIO()
    wb.save(output)
    drive = drive_service()
    folder = drive.files().get(fileId=FOLDER, fields="id,mimeType,trashed,capabilities/canAddChildren").execute()
    if folder.get("trashed") or folder.get("mimeType") != "application/vnd.google-apps.folder" or not folder.get("capabilities", {}).get("canAddChildren", False):
        raise RuntimeError("Salary backup folder is unavailable or read-only")
    stamp = timezone.localtime().strftime("%Y-%m-%d_%H-%M")
    files = []
    for extension, payload in (("json", raw), ("xlsx", output.getvalue())):
        nonce = secrets.token_bytes(12)
        encrypted = MAGIC + nonce + AESGCM(key).encrypt(nonce, payload, MAGIC)
        name = f"MoliApp-Maas-{stamp}.{extension}.enc"
        uploaded = drive.files().create(
            body={"name": name, "parents": [FOLDER], "description": "Encrypted MoliApp salary backup"},
            media_body=MediaIoBaseUpload(io.BytesIO(encrypted), mimetype="application/octet-stream", resumable=True),
            fields="id,size",
        ).execute()
        remote = drive.files().get(fileId=uploaded["id"], fields="id,size,trashed").execute()
        if remote.get("trashed") or int(remote.get("size", -1)) != len(encrypted):
            raise RuntimeError("Salary backup upload verification failed: " + extension)
        files.append({"file_id": uploaded["id"], "size": len(encrypted), "type": extension})
    return {"file_id": files[0]["file_id"], "size": sum(f["size"] for f in files), "records": sum(len(v) for v in data["models"].values()), "files": files}
