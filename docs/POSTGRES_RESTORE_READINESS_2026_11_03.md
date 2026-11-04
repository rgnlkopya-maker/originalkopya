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

## 2026-11-04 progress
- Daily automated module backups verified from production records: folios 27 records, 6 changed/new files, completion 00:28 Istanbul; instruments 16 records, 2 new files, completion 00:11 Istanbul. These records do not establish physical archive integrity.
- Added read-only Django management command `backup_table_audit` on isolated backup branch. It captures table names and row counts, compares with a separately captured manifest after restore, rejects table or row count differences and refuses to overwrite a prior manifest.
- Added five unit-test cases, but tests have not yet been executed on a Django runtime; code is NOT deployed to main.
- Reminder: a pre-restore and post-restore comparison must use the same recovery snapshot. Running baseline against a live database at a different time would create false mismatches.
- Outstanding: encrypted real PostgreSQL dump, independent storage and a successful isolated pg_restore test, plus credential rotation.

## 2026-11-04 restore audit correction
- Fixed a false-negative in the comparison: an isolated restore database can have a different database name from production. Database name is recorded for traceability, but is no longer required to match.
- PostgreSQL major version now uses the numeric server_version_num convention, and malformed version metadata is reported.
- Added two unit tests: isolated destination database name and malformed PostgreSQL version.
- The code changes were committed to the isolated backup branch only. Full Django tests have not run: the local verification environment lacks Django and package installation was unavailable. Do not mark these tests passed.
- No production dump, backup upload, restore, scheduled-task or secret changes occurred.

## 2026-11-04 verification update
- Ran seven isolated Python unit tests for the exact comparison logic with a local Python harness: 7/7 pass (same counts, changed counts, missing and unexpected table, major version change, alternate restore database name, invalid version metadata).
- This was not the Django test suite; Django is unavailable in the local runtime, and package installation failed. Full command integration remains unverified.
- Adjusted the audit count collection to use a read-only REPEATABLE READ transaction so counts form a consistent snapshot. Code remains only in the isolated development branch.
- No real pg_dump, encrypted upload or restore performed. Production and current scheduled backups unchanged.
