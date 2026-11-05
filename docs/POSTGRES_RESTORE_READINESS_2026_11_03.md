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

## 2026-11-04 Django CI test setup
- Local runtime lacks Django and PostgreSQL client. Installing Django was blocked by network/DNS; no Django test result can be claimed locally.
- Added isolated GitHub Actions workflow at .github/workflows/backup-recovery-tests.yml, pinned to the backup preparation branch and with read-only repository permissions. It installs Django 5.2.6 and runs the seven comparison tests without a production database or credentials.
- Workflow outcome has not yet been verified. A successful run is required before marking the Django test stage complete.
- Actual PostgreSQL dump and isolated restore remain pending. Main branch and live services unchanged.

## 2026-11-04 — Test execution and implementation gate
- Local encrypted-stream backup prototype was rerun via `python -m unittest -v test_moliapp_pg_backup_stream.py`: five tests passed (roundtrip, tamper rejection, failed dump rejection, absent/existing output, connection-secret environment handling). This does not use production data, a PostgreSQL client, or pg_restore.
- GitHub Actions YAML exists on branch `backup-recovery-prep-2026-11-03`; the available GitHub connector returned no commit statuses or PR-triggered workflow runs. A successful Django CI run cannot be independently asserted.
- This container has no Django or pg_dump; pip installation could not reach the package index (DNS failure). Do not mark real dump, restore, or Django integration as passed.
- Security gate: rotate the exposed backup-scheduler credential in a coordinated cutover before deploying new background jobs. Do not commit secrets, connection strings, or a live database dump.
- Next executable stage requires a secure PostgreSQL-18 client runner, encrypted offsite storage and separate key custody; restore must target a dedicated isolated DB. Current production database remains unchanged.

## 2026-11-04 — isolated test coverage extension
- Added two additional test cases to the recovery table-audit suite: enforce a REPEATABLE READ READ ONLY counting transaction and reject malformed table manifests. There are now nine Django test cases in the development branch.
- Django is not installed in the local execution environment; installation was unsuccessful. The nine Django tests are NOT marked executed or passed.
- Re-ran five separate encrypted-stream prototype tests successfully with Python unittest in /mnt/data. Those tests do not represent a real PostgreSQL dump or restore.
- Existing live main branch, backup cron, database and secrets remain unchanged.
- Next proof required: actual Django CI execution, encrypted PG18 dump with secure runner, and restore into dedicated isolated DB.

## 2026-11-04 — manifest integrity hardening
- Hardened the recovery comparator to reject missing/empty table inventories, negative and boolean row counts, invalid PostgreSQL version metadata, missing format version and non-object manifests. A legitimate isolated restore may still have a different database name.
- Added seven regression cases on the separate recovery-preparation branch: missing/empty tables, negative/boolean counts, missing format/version, invalid manifest root. Total Django test cases on the branch: 16.
- Test execution status: 16 Django test cases remain unverified in a real Django runtime. The local environment has no Django and package-index access failed; GitHub connector did not prove a successful CI run. Do not report these tests as passed.
- Security/production: no deployment, backup job or live database data changes. No real full encrypted pg_dump or isolated restore completed.

## 2026-11-04 — critical simplification: Render native recovery
- Verified via Render get_postgres: production instance `originalkopya-db`, PostgreSQL 18, paid compute plan `0.5c-1g`, Frankfurt. Production web app is on main and auto-deploy; the preparation branch remains isolated.
- Render official docs confirm paid PostgreSQL instances have managed point-in-time recovery (3 days Hobby workspace, 7 days Pro+). This is a native database recovery path; availability of a particular recovery point must be checked on the database Recovery dashboard.
- Render's Recovery page also supports manual `Create export` for a full logical database backup, retained on Render for 7 days; this export must be downloaded to independent storage for long-term/off-Render recovery.
- Direct action to unblock: open https://dashboard.render.com/d/dpg-dach0t2fngtc73dfigg0-a , navigate Recovery and trigger Create export. The available connector exposes no Create export or PITR action, so no export has been initiated by this assistant.
- Shortest proof route: native export -> verify archive -> independent encrypted storage -> restore to *new isolated* database; photos/files require separate verification. Stop writing additional comparator tests until a real archive exists.

## 2026-11-05 — actual external backup integrity verification
- The user exported Render's PostgreSQL directory archive and uploaded it to a private Google Drive folder `MoliApp Yedekleri`. Google Drive file: `2026-11-05T05_05Z.dir.tar.gz`, id `1VFiRfEgAPQHl6lDkqqwmQYghyIp-t7lh`, size 907183 bytes.
- The archive was downloaded through the authenticated Drive connector and verified locally, without changing any production data.
- SHA-256 of the compressed archive: `5af54f911537f9ac5541a88ae5bfc947530c3847e51acc0ec68cc3faa1766b74`.
- Tar gzip stream fully readable, with 119 files totaling 9559454 bytes (one `toc.dat` plus 118 table-data `.dat` members). TOC has PostgreSQL `PGDMP` magic header. All 118 data members have PostgreSQL COPY end markers; 96 contain rows and 22 appear empty.
- This is a meaningful on-disk structural integrity test, NOT a successful `pg_restore`, logical correctness check or application recovery proof. Local runtime lacks PostgreSQL client and server tools. No isolated restore has been run.
- Archive is not encrypted and must remain private. Further work: test `pg_restore` only against a dedicated isolated PostgreSQL 18 instance and then verify application/media recovery. Avoid adding unrelated unit tests.
