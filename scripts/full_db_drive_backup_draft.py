"""One-shot, encrypted full PostgreSQL backup to the existing private Google Drive.

Not deployed. Requires pg_dump client matching server major version (18),
DATABASE_URL, MOLI_DB_BACKUP_KEY (32 random bytes, urlsafe base64), and
a connected Google Drive account. Never runs in an HTTP request.
"""
import base64
import hashlib
import io
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from googleapiclient.http import MediaFileUpload

DRIVE_ROOT = "1Q-KUwSudqqsyu72Eigsrx7YZfoTUp3mu"
MAGIC = b"MOLI-PG-BACKUP-1\n"
CHUNK = 1024 * 1024


def run_backup():
    from core.instrument_drive_oauth import connected, drive_service
    from core.instrument_backup_views import _folder

    url = os.environ.get("DATABASE_URL", "")
    parsed = urlsplit(url)
    if parsed.scheme not in ("postgres", "postgresql") or not parsed.hostname:
        raise RuntimeError("Missing PostgreSQL DATABASE_URL")
    if not connected():
        raise RuntimeError("Google Drive connection is missing")
    key_text = os.environ.get("MOLI_DB_BACKUP_KEY", "")
    try:
        key = base64.b64decode(key_text, altchars=b"-_", validate=True)
    except Exception as exc:
        raise RuntimeError("Backup encryption key is not configured") from exc
    if len(key) != 32:
        raise RuntimeError("Backup encryption key must be 32 bytes")
    dump_bin = os.environ.get("PG_DUMP_BIN", "pg_dump")
    version = subprocess.run([dump_bin, "--version"], check=True, capture_output=True, text=True)
    if " 18." not in version.stdout:
        raise RuntimeError("PostgreSQL 18 pg_dump client required")

    nonce = secrets.token_bytes(12)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(MAGIC)
    env = os.environ.copy()
    env["PGCONNECT_TIMEOUT"] = "15"
    command = [dump_bin, "--dbname", url, "--format=custom", "--no-owner", "--no-acl"]
    # The URL contains a password; never log command or process argv.
    # Prefer libpq env variables in a production runner; this prototype is
    # intentionally blocked until the URL is removed from argv.
    raise RuntimeError("Production execution blocked: DB credentials must not appear in process arguments")


def validate_drive_upload(drive, file_id, expected_size):
    metadata = drive.files().get(fileId=file_id, fields="id,size,trashed").execute()
    if metadata.get("trashed") or int(metadata.get("size", -1)) != expected_size:
        raise RuntimeError("Drive upload size mismatch")
