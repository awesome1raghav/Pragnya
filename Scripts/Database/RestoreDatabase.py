"""Restore a NEXTRON backup into a new database and a new storage root, then verify it.

Usage (repository root):
  .\.venv\Scripts\python.exe -m Scripts.Database.RestoreDatabase <backup directory> --database <new database name> --storage <new folder>

The new database is created on the server in DATABASE_URL (it must not exist yet) and the storage folder must be new
or empty: a restore never writes over the live data. Verification compares the migration head, every table's row count
and every evidence file's SHA-256 with the backup's manifest. To switch NEXTRON to the restored copy, point
DATABASE_URL and STORAGE_ROOT at it.
"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from Backend.App.Config import get_settings
from Backend.App.Services import Backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("backup", type=Path)
    parser.add_argument("--database", required=True, help="name of the new database to create")
    parser.add_argument("--storage", type=Path, required=True, help="new, empty storage root")
    args = parser.parse_args()
    s = get_settings()
    server = make_url(s.DATABASE_URL)
    admin = create_engine(server.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as c:
            if c.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": args.database}).first():
                print(f"Database {args.database} already exists; choose a new name", file=sys.stderr)
                return 1
            c.execute(text(f'CREATE DATABASE "{args.database}"'))
    finally:
        admin.dispose()
    target = server.set(database=args.database).render_as_string(hide_password=False)
    try:
        report = Backup.restore_backup(args.backup, s.BACKUP_ENCRYPTION_KEY.get_secret_value(), target, args.storage)
    except Backup.BackupError as exc:
        print(f"Restore failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
