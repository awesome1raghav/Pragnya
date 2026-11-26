"""NEX-EVD integrity: recompute SHA-256 of stored bytes and compare with the recorded digest.

The recorded digest is never changed. Every verification, including a mismatch or a missing
file, is committed as a custody event.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from Backend.App.Modules.NexEvd import ChainOfCustody
from Backend.App.Modules.NexEvd.HashService import digest_stream
from Backend.App.Modules.NexEvd.Schemas import IntegrityState, IntegrityVerification
from Backend.App.Realtime import Outbox
from Backend.App.Storage.StorageInterface import EvidenceStorage, StorageError
from Database.PostgreSQL.Models import Evidence
from Database.PostgreSQL.Repositories import EventRepository

_RESULT_EVENT = {
    "MATCH": ChainOfCustody.INTEGRITY_VERIFIED,
    "MISMATCH": ChainOfCustody.INTEGRITY_MISMATCH,
    "MISSING": ChainOfCustody.INTEGRITY_MISSING,
}


def verify(session: Session, storage: EvidenceStorage, evidence: Evidence, actor: str) -> IntegrityVerification:
    computed_sha256: str | None = None
    computed_size: int | None = None
    try:
        with storage.open_original(evidence.storage_key) as stored:
            computed_sha256, computed_size = digest_stream(stored)
        result = "MATCH" if (computed_sha256, computed_size) == (evidence.sha256, evidence.size_bytes) else "MISMATCH"
    except StorageError:
        result = "MISSING"

    verified_at = datetime.now(timezone.utc)
    verification = IntegrityVerification(
        evidence_id=evidence.id,
        result=result,
        recorded_sha256=evidence.sha256,
        computed_sha256=computed_sha256,
        recorded_size=evidence.size_bytes,
        computed_size=computed_size,
        verified_at=verified_at,
    )
    ChainOfCustody.record(session, evidence, _RESULT_EVENT[result], actor, verification.model_dump(mode="json", exclude={"note"}))
    Outbox.publish(session, f"evidence.integrity_{result.lower()}", aggregate_type="evidence", aggregate_id=evidence.id,
                   case_id=evidence.case_id, payload={"evidence_number": evidence.display_number, "result": result})
    session.commit()
    return verification


def state(session: Session, evidence: Evidence) -> IntegrityState:
    last = EventRepository.latest_of_types(session, evidence_id=evidence.id, event_types=ChainOfCustody.INTEGRITY_EVENTS)
    return IntegrityState(
        evidence_id=evidence.id,
        recorded_sha256=evidence.sha256,
        recorded_size=evidence.size_bytes,
        preserved_at=evidence.preserved_at,
        last_verification=IntegrityVerification.model_validate(last.payload) if last else None,
    )
