"""Encrypted, one-shot full PostgreSQL backup to private Google Drive.

Run only in a trusted background worker, not inside an HTTP request.
Prerequisites: PostgreSQL 18 pg_dump, DATABASE_URL, MOLI_DB_BACKUP_KEY
(32 random bytes encoded with URL-safe base64), and existing Drive OAuth.
This module is not scheduled or deployed.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
from urllib.parse import urlsplit, unquote

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from googleapiclient.http import MediaFileUpload
from django.utils import timezone

DRIVE_ROOT = "1Q-KUwSudqqsyu72Eigsrx7YZfoTUp3mu"
MAGIC = b"MOLI-PG-BACKUP-1\n"
CHUNK = 1024 * 1024


def _db_env():
    url = os.environ.get("DATABASE_URL", "")
    p = urlsplit(url)
    if p.scheme not in ("postgres", "postgresql") or not p.hostname or not p.path.strip("/"):
        raise RuntimeError("DATABASE_URL is missing or invalid")
    env = os.environ.copy()
    env.update(PGHOST=p.hostname, PGPORT=str(p.port or 5432),
               PGDATABASE=unquote(p.path.lstrip("/")), PGUSER=unquote(p.username or ""),
               PGPASSWORD=unquote(p.password or ""), PGCONNECT_TIMEOUT="15")
    # No password-bearing URL is passed to subprocess argv.
    if not env["PGPASSWORD"]:
        raise RuntimeError("Database password is missing")
    if "sslmode=" in p.query:
        from urllib.parse import parse_qs
        env["PGSSLMODE"] = parse_qs(p.query)["sslmode"][0]
    return env


def _encryption_key():
    try:
        key = base64.urlsafe_b64decode(os.environ["MOLI_DB_BACKUP_KEY"] + "=" * (-len(os.environ["MOLI_DB_BACKUP_KEY"]) % 4))
    except (KeyError, ValueError) as exc:
        raise RuntimeError("MOLI_DB_BACKUP_KEY is missing or invalid") from exc
    if len(key) != 32:
        raise RuntimeError("MOLI_DB_BACKUP_KEY must decode to 32 bytes")
    return key


def _encrypt_file(source, destination, key):
    nonce = secrets.token_bytes(12)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(MAGIC)
    with open(source, "rb") as inp, open(destination, "wb") as out:
        out.write(MAGIC + nonce)
        while True:
            chunk = inp.read(CHUNK)
            if not chunk:
                break
            out.write(encryptor.update(chunk))
        out.write(encryptor.finalize())
        out.write(encryptor.tag)


def run_backup():
    from core.instrument_drive_oauth import connected, drive_service
    from core.instrument_backup_views import _folder

    key = _encryption_key()
    env = _db_env()
    if not connected():
        raise RuntimeError("Google Drive is not connected")
    binary = os.environ.get("PG_DUMP_BIN", "/usr/lib/postgresql/18/bin/pg_dump")
    version = subprocess.run([binary, "--version"], check=True, capture_output=True, text=True, timeout=15)
    if " 18." not in version.stdout:
        raise RuntimeError("PostgreSQL 18 pg_dump client is required")
    stamp = timezone.now().strftime("%Y-%m-%dT%H-%M-%SZ")
    with tempfile.TemporaryDirectory(prefix="moli-pg-") as temp:
        plain = Path(temp) / "backup.dump"
        encrypted = Path(temp) / "backup.dump.enc"
        command = [binary, "--format=custom", "--no-owner", "--no-acl", "--file", str(plain)]
        # stderr can contain connection details; do not log it.
        result = subprocess.run(command, env=env, capture_output=True, timeout=600)
        if result.returncode:
            raise RuntimeError("pg_dump failed (details withheld)")
        if plain.stat().st_size < 100 or plain.open("rb").read(5) != b"PGDMP":
            raise RuntimeError("Invalid pg_dump archive")
        _encrypt_file(plain, encrypted, key)
        drive = drive_service()
        root = _folder(drive, DRIVE_ROOT, "Tam Veritabani Yedekleri")
        name = f"MoliApp-Full-{stamp}.dump.enc"
        created = drive.files().create(
            body={"name": name, "parents": [root],
                  "description": "AES-256-GCM encrypted PostgreSQL 18 custom dump"},
            media_body=MediaFileUpload(str(encrypted), mimetype="application/octet-stream", resumable=True),
            fields="id,size,md5Checksum",
        ).execute()
        expected = encrypted.stat().st_size
        remote = drive.files().get(fileId=created["id"], fields="id,size,trashed").execute()
        if remote.get("trashed") or int(remote.get("size", -1)) != expected:
            raise RuntimeError("Drive upload size verification failed")
        return {"id": remote["id"], "bytes": expected, "created_at": stamp}
