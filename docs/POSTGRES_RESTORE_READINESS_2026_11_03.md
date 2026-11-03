# MoliApp PostgreSQL restore readiness (2026-11-03)

Status: preparation only. No production database export or restore has been performed.

Verified using read-only database queries:
- PostgreSQL version: 18.6
- Database size: approximately 33 MB
- Public tables: 118
- Tables readable by application role: 118 of 118
- Materialized views: 0
- Existing module exports are not full database backups.

Acceptance steps before completion:
1. Use PostgreSQL 18 client tooling for a full custom-format dump.
2. Encrypt the backup before persistent storage; keep the encryption key separate from the archive.
3. Upload encrypted data to independent storage with checksums and retention.
4. Restore only into an isolated database, never over production.
5. Compare tables, row counts, application relations and media links.
6. Record successful restore proof and recovery time.

Security: The backup scheduler currently risks exposing its credential in command/log output. Rotate that credential with a coordinated service-and-scheduler change; do not paste its value into GitHub.
