"""Encrypted backup of the NEXTRON database and evidence storage.

Usage (repository root):
  .\.venv\Scripts\python.exe -m Scripts.Database.BackupDatabase [--out <directory>]
  .\.venv\Scripts\python.exe -m Scripts.Database.BackupDatabase --new-key      # print a fresh key for BACKUP_ENCRYPTION_KEY

Reads DATABASE_URL, STORAGE_ROOT and BACKUP_ENCRYPTION_KEY from Backend/.env. Writes NEXTRON-<UTC time>/ under --out
(default: BACKUP_DIR, which defaults to Backups/ in the repository, ignored by Git). See Backend/App/Services/Backup.py.
"""

import argparse
import json
import sys
from pathlib import Path

from Backend.App.Config import get_settings
from Backend.App.Services import Backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--new-key", action="store_true", help="print a new random key and exit")
    args = parser.parse_args()
    if args.new_key:
        print(Backup.new_key())
        return 0
    s = get_settings()
    try:
        result = Backup.create_backup(s.DATABASE_URL, Path(s.STORAGE_ROOT), args.out or Path(s.BACKUP_DIR),
                                      s.BACKUP_ENCRYPTION_KEY.get_secret_value())
    except Backup.BackupError as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1
    m = result.manifest
    print(json.dumps({"backup": str(result.path), "alembic_head": m["alembic_head"], "rows": sum(m["row_counts"].values()),
                      "evidence": len(m["evidence"]), "bytes": {k: v["bytes"] for k, v in m["parts"].items()}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
