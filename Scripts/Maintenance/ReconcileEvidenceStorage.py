"""Report differences between evidence storage and the evidence table.

Run from the repository root:
    .\\.venv\\Scripts\\python.exe -m Scripts.Maintenance.ReconcileEvidenceStorage
    .\\.venv\\Scripts\\python.exe -m Scripts.Maintenance.ReconcileEvidenceStorage --delete-stale-staging

Never deletes or moves originals. Exit code 0 when clean, 1 when anything needs attention.
"""

import argparse
import json
from datetime import timedelta

from Backend.App.Config import get_settings
from Backend.App.Modules.NexEvd.StorageReconciliation import reconcile
from Backend.App.Storage.LocalStorage import LocalStorage
from Database.PostgreSQL.Connection import EngineOptions, create_database_engine
from Database.PostgreSQL.Session import create_session_factory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stale-minutes", type=int, default=60, help="Staging files older than this are stale (default 60)")
    parser.add_argument("--delete-stale-staging", action="store_true", help="Delete stale staging files")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_database_engine(settings.DATABASE_URL, EngineOptions(pooled=False, application_name="nextron-reconcile"))
    try:
        with create_session_factory(engine)() as session:
            report = reconcile(
                session,
                LocalStorage(settings.STORAGE_ROOT),
                stale_after=timedelta(minutes=args.stale_minutes),
                delete_stale_staging=args.delete_stale_staging,
            )
    finally:
        engine.dispose()

    print(json.dumps({
        "checked_at": report.checked_at.isoformat(),
        "clean": report.clean,
        "referenced_originals": report.referenced_originals,
        "orphan_originals": report.orphan_originals,
        "missing_originals": report.missing_originals,
        "stale_staging": report.stale_staging,
        "deleted_staging": report.deleted_staging,
    }, indent=2))
    return 0 if report.clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
