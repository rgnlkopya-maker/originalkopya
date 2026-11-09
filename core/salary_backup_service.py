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
    nonce = secrets.token_bytes(12)
    encrypted = MAGIC + nonce + AESGCM(key).encrypt(nonce, raw, MAGIC)
    drive = drive_service()
    folder = drive.files().get(fileId=FOLDER, fields="id,mimeType,trashed,capabilities/canAddChildren").execute()
    if folder.get("trashed") or folder.get("mimeType") != "application/vnd.google-apps.folder" or not folder.get("capabilities", {}).get("canAddChildren", False):
        raise RuntimeError("Salary backup folder is unavailable or read-only")
    stamp = timezone.localtime().strftime("%Y-%m-%d_%H-%M")
    name = f"MoliApp-Maas-{stamp}.json.enc"
    uploaded = drive.files().create(
        body={"name": name, "parents": [FOLDER], "description": "Encrypted monthly MoliApp salary snapshot"},
        media_body=MediaIoBaseUpload(io.BytesIO(encrypted), mimetype="application/octet-stream", resumable=True),
        fields="id,size",
    ).execute()
    remote = drive.files().get(fileId=uploaded["id"], fields="id,size,trashed").execute()
    if remote.get("trashed") or int(remote.get("size", -1)) != len(encrypted):
        raise RuntimeError("Salary backup upload verification failed")
    return {"file_id": uploaded["id"], "size": len(encrypted), "records": sum(len(v) for v in data["models"].values())}
