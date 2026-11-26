# Backup and Recovery

## What a backup contains

`Scripts/Database/BackupDatabase.py` writes `Backups/NEXTRON-<UTC time>/` (git-ignored; set `BACKUP_DIR` to put it
elsewhere, ideally another disk):

| File | Contents |
|---|---|
| `database.dump.enc` | `pg_dump` (custom format) of the NEXTRON database, encrypted |
| `storage.tar.enc` | `Originals/`, `Derived/` and `Reports/` under `STORAGE_ROOT`, encrypted (staging files are not kept) |
| `manifest.json` | Migration head, row count of every table, every evidence item's SHA-256 and storage key, SHA-256 of both parts |

Encryption: AES-256-GCM in 8 MiB chunks, each authenticated with its position and a last-chunk flag, so a changed,
reordered or truncated file is refused. The key is `BACKUP_ENCRYPTION_KEY` in `Backend/.env` and is never written into a
backup. **Keep a copy of the key somewhere other than this machine; without it no backup can be restored.**

Neo4j and Qdrant are not backed up: they are projections and are rebuilt from PostgreSQL
(`POST /api/v1/system/projections/neo4j/rebuild`, `Scripts/Maintenance/RebuildVisualIndex.py`).

## Commands (repository root)

```powershell
.\.venv\Scripts\python.exe -m Scripts.Database.BackupDatabase --new-key
```
Prints a new key. Put it in `Backend/.env` as `BACKUP_ENCRYPTION_KEY` once, and store a copy elsewhere.

```powershell
.\.venv\Scripts\python.exe -m Scripts.Database.BackupDatabase
```
Makes a backup. `pg_dump` runs inside the `nextron-postgres` container (`PG_TOOLS=docker:nextron-postgres`); set
`PG_TOOLS=local` to use PostgreSQL 17 client tools from PATH.

```powershell
.\.venv\Scripts\python.exe -m Scripts.Database.RestoreDatabase Backups\NEXTRON-<time> --database nextron_restored --storage D:\NEXTRON-Restored
```
Restores into a **new** database and a **new or empty** folder, never over the live data, then verifies migration head,
every table's row count and every evidence file's SHA-256 against the manifest. It prints the verification report and
exits non-zero on any difference.

To switch NEXTRON to a restored copy: stop the API and worker, point `DATABASE_URL` and `STORAGE_ROOT` at it, start them,
then rebuild the projections.

## Restore drill (26 November 2026)

Live development data: 22 tables, 7,858 rows, 84 evidence items. Backup 5.5 MB. Restored into a new database and folder:
verification `ok`, 84 of 84 evidence SHA-256 values equal. The drill copy was then deleted. `Tests/Integration/PostgreSQL/test_backup_restore.py`
repeats this on every test run, and checks that a wrong key, a changed byte, a truncated file and a non-empty target are
refused.

## Outages

`Scripts/Testing/OutageDrill.py` stops and restarts the local containers and reports what NEXTRON did:

| Outage | Observed (26 November 2026) |
|---|---|
| PostgreSQL stopped | `/health/ready` 503 within 3 s; a write answers 503 `DATABASE_UNAVAILABLE` and is not stored; the worker stays up |
| PostgreSQL restarted | Ready again in 0.6 s; worker heartbeating at once; a new run completed |
| Neo4j stopped | Uploads and runs still complete; `/system/projections` shows Neo4j unreachable and the lag |
| Neo4j restarted | Lag back to 0 after 17 s |
