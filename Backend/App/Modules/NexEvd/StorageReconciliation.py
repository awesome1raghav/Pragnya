"""Compare storage with the evidence table after a crash or outage.

Reports, never repairs evidence:
  - orphan originals: bytes in Originals/ with no evidence row (crash between promote and commit)
  - missing originals: evidence rows whose bytes are absent (serious; investigate)
  - stale staging files: interrupted uploads older than a threshold (safe to delete)
Only stale staging files may be deleted, and only when asked.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from Backend.App.Storage.StorageInterface import EvidenceStorage
from Database.PostgreSQL.Repositories import EvidenceRepository


@dataclass
class ReconciliationReport:
    checked_at: datetime
    referenced_originals: int
    orphan_originals: list[str] = field(default_factory=list)
    missing_originals: list[str] = field(default_factory=list)
    stale_staging: list[str] = field(default_factory=list)
    deleted_staging: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (self.orphan_originals or self.missing_originals or self.stale_staging)


def reconcile(
    session: Session, storage: EvidenceStorage, *, stale_after: timedelta = timedelta(hours=1), delete_stale_staging: bool = False
) -> ReconciliationReport:
    now = datetime.now(timezone.utc)
    referenced = EvidenceRepository.all_storage_keys(session)
    stored = set(storage.iter_original_keys())

    report = ReconciliationReport(checked_at=now, referenced_originals=len(referenced))
    report.orphan_originals = sorted(stored - referenced.keys())
    report.missing_originals = sorted(str(referenced[key]) for key in referenced.keys() - stored)

    for staged in storage.iter_staging():
        if now - staged.modified_at >= stale_after:
            report.stale_staging.append(staged.path.name)
            if delete_stale_staging:
                storage.discard_staging(staged.path)
                report.deleted_staging.append(staged.path.name)
    report.stale_staging.sort()
    return report
