"""NEX-EVD Evidence Preservation.

Order of operations (archive §12.2):
  1. Staged bytes were hashed while streaming (NEX-CAP).
  2. Promote them to a fresh, read-only original key.
  3. Re-read the original and confirm digest and size match what was received.
  4. Commit the evidence row and its custody events in one transaction.
If step 4 fails, the unreferenced original is removed. A crash between 2 and 4 leaves an
orphan original with no record; StorageReconciliation reports it. A row is never written
for bytes that are not verified in storage, so every evidence row means PRESERVED.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Modules.NexCap.FileAcquisition import ReceivedUpload
from Backend.App.Modules.NexCap.Validation import MediaIdentification
from Backend.App.Modules.NexCm import Lifecycle
from Backend.App.Modules.NexCm.Service import get_case
from Backend.App.Modules.NexEvd import ChainOfCustody
from Backend.App.Modules.NexEvd.HashService import ALGORITHM, digest_stream
from Backend.App.Realtime import Outbox
from Backend.App.Storage.StorageInterface import EvidenceStorage, StorageError, original_key
from Database.PostgreSQL.Models import Evidence
from Database.PostgreSQL.Repositories import EventRepository, EvidenceRepository


@dataclass(frozen=True)
class AcquisitionContext:
    source_type: str
    acquisition_method: str
    description: str | None
    received_at: datetime


def get_evidence(session: Session, evidence_id: uuid.UUID) -> Evidence:
    evidence = EvidenceRepository.get(session, evidence_id)
    if evidence is None:
        raise NextronError(404, ErrorCode.EVIDENCE_NOT_FOUND, "The requested evidence does not exist")
    return evidence


def preserve(
    session: Session,
    storage: EvidenceStorage,
    *,
    case_id: uuid.UUID,
    upload: ReceivedUpload,
    media: MediaIdentification,
    context: AcquisitionContext,
    actor: str,
    before_commit: Callable[[Session, Evidence], None] | None = None,
) -> tuple[Evidence, list[Evidence]]:
    """Returns the committed evidence and earlier evidence in the case with identical bytes.

    `before_commit` adds work that must exist exactly when the evidence does (NEX-CAP queues its analysis run here).
    """
    case = get_case(session, case_id, for_update=True)  # holds the case row until commit
    Lifecycle.ensure_writable(case)

    evidence_id = uuid.uuid4()
    key = original_key(case_id, evidence_id)
    try:
        storage.promote_original(upload.staged_path, key)
    except StorageError as exc:
        session.rollback()  # promote never leaves a partial original behind, so nothing to remove
        raise NextronError(503, ErrorCode.STORAGE_UNAVAILABLE, "Evidence storage failed; nothing was preserved") from exc
    try:
        with storage.open_original(key) as stored:
            stored_sha256, stored_size = digest_stream(stored)
    except (StorageError, OSError) as exc:
        session.rollback()
        _remove_quietly(storage, key)
        raise NextronError(503, ErrorCode.STORAGE_UNAVAILABLE, "Evidence storage failed; nothing was preserved") from exc

    if (stored_sha256, stored_size) != (upload.sha256, upload.size_bytes):
        session.rollback()
        _remove_quietly(storage, key)
        raise NextronError(
            500, ErrorCode.PRESERVATION_FAILED, "Stored bytes did not match the received bytes; nothing was preserved"
        )

    try:
        evidence = Evidence(
            id=evidence_id,
            case_id=case_id,
            original_filename=upload.filename,
            declared_content_type=upload.declared_content_type,
            media_type=media.media_type,
            detected_format=media.detected_format,
            mime_type=media.mime_type,
            size_bytes=upload.size_bytes,
            sha256=upload.sha256,
            storage_key=key,
            preservation_status="PRESERVED",
            source_type=context.source_type,
            acquisition_method=context.acquisition_method,
            description=context.description,
            acquired_by=actor,
            received_at=context.received_at,
        )
        session.add(evidence)
        session.flush()
        duplicates = EvidenceRepository.same_hash_in_case(session, case_id, upload.sha256, exclude_id=evidence_id)

        ChainOfCustody.record(session, evidence, ChainOfCustody.RECEIVED, actor, {
            "filename": upload.filename,
            "declared_content_type": upload.declared_content_type,
            "source_type": context.source_type,
            "acquisition_method": context.acquisition_method,
            "received_at": context.received_at.isoformat(),
        })
        ChainOfCustody.record(session, evidence, ChainOfCustody.HASHED, actor, {
            "algorithm": ALGORITHM, "sha256": upload.sha256, "size_bytes": upload.size_bytes, "computed": "server-side while streaming",
        })
        ChainOfCustody.record(session, evidence, ChainOfCustody.PRESERVED, actor, {
            "sha256": stored_sha256,
            "size_bytes": stored_size,
            "storage_verified": True,
            "media_type": media.media_type,
            "detected_format": media.detected_format,
            "mime_type": media.mime_type,
            "duplicate_of": [str(d.id) for d in duplicates],
        })
        new_status = Lifecycle.on_evidence_preserved(case)
        if new_status:
            case.revision += 1
            EventRepository.append(session, case_id=case_id, event_type="case.status_changed", actor=actor,
                                   payload={"to_status": new_status, "reason": "first evidence preserved", "revision": case.revision})
        Outbox.publish(session, "evidence.created", aggregate_type="evidence", aggregate_id=evidence.id, case_id=case_id, payload={
            "evidence_number": evidence.display_number, "media_type": media.media_type, "sha256": upload.sha256,
            "size_bytes": upload.size_bytes, "case_status": case.status,
        })
        if before_commit is not None:
            before_commit(session, evidence)
        session.commit()
    except Exception:
        session.rollback()
        _remove_quietly(storage, key)
        raise

    session.refresh(evidence)
    return evidence, duplicates


def _remove_quietly(storage: EvidenceStorage, key: str) -> None:
    try:
        storage.remove_unreferenced_original(key)
    except (StorageError, OSError):
        pass  # left for StorageReconciliation to report
