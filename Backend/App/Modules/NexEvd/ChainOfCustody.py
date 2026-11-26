"""NEX-EVD chain of custody: every custody action becomes an append-only investigation event."""

from typing import Any

from sqlalchemy.orm import Session

from Database.PostgreSQL.Models import Evidence, InvestigationEvent
from Database.PostgreSQL.Repositories import EventRepository

RECEIVED = "evidence.received"
HASHED = "evidence.hashed"
PRESERVED = "evidence.preserved"
METADATA_EXTRACTED = "evidence.metadata_extracted"
METADATA_UNAVAILABLE = "evidence.metadata_unavailable"
METADATA_FAILED = "evidence.metadata_failed"
INTEGRITY_VERIFIED = "evidence.integrity_verified"
INTEGRITY_MISMATCH = "evidence.integrity_mismatch"
INTEGRITY_MISSING = "evidence.integrity_missing"
DOWNLOADED = "evidence.downloaded"

INTEGRITY_EVENTS = (INTEGRITY_VERIFIED, INTEGRITY_MISMATCH, INTEGRITY_MISSING)


def record(session: Session, evidence: Evidence, event_type: str, actor: str, payload: dict[str, Any]) -> InvestigationEvent:
    return EventRepository.append(
        session, case_id=evidence.case_id, evidence_id=evidence.id, event_type=event_type, actor=actor, payload=payload
    )
