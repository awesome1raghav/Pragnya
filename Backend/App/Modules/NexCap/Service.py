"""NEX-CAP Evidence Acquisition: receive an upload, validate it, hand it to NEX-EVD, queue its analysis.

Blocking work (database, hashing the stored copy, FFprobe identification) runs in the thread pool,
each step with its own short session, so the event loop only streams the request body.
Analysis does not run in the request: with AUTO_ANALYZE_ON_UPLOAD the evidence commit also queues a
T-MIR investigation run for it (same transaction), which a worker picks up. NEX-MET runs there.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request

from Backend.App.Config import Settings
from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Services import Preferences
from Backend.App.Modules.NexCap.FileAcquisition import ReceivedUpload, receive_upload
from Backend.App.Modules.NexCap.Validation import identify_media
from Backend.App.Modules.NexCm import Lifecycle
from Backend.App.Modules.NexCm.Service import get_case
from Backend.App.Modules.NexEvd import Service as EvidenceService
from Backend.App.Contracts.ExecutionStates import JobType
from Backend.App.Modules.NexEvd.Schemas import DuplicateReference, EvidenceRead, JobReference, UploadedEvidence
from Backend.App.Storage.LocalStorage import LocalStorage
from Backend.App.Workers import JobService
from Database.PostgreSQL.Models.Evidence import ACQUISITION_METHODS, SOURCE_TYPES

FILE_FIELD = "file"
TEXT_FIELDS = frozenset({"source_type", "acquisition_method", "description"})
MAX_DESCRIPTION = 2000


def _context(upload: ReceivedUpload, received_at: datetime) -> EvidenceService.AcquisitionContext:
    fields = upload.fields
    source_type = fields.get("source_type", "USER_UPLOAD").strip() or "USER_UPLOAD"
    method = fields.get("acquisition_method", "DIRECT_UPLOAD").strip() or "DIRECT_UPLOAD"
    description = (fields.get("description") or "").strip() or None
    problems = {}
    if source_type not in SOURCE_TYPES:
        problems["source_type"] = f"Must be one of {list(SOURCE_TYPES)}"
    if method not in ACQUISITION_METHODS:
        problems["acquisition_method"] = f"Must be one of {list(ACQUISITION_METHODS)}"
    if description and len(description) > MAX_DESCRIPTION:
        problems["description"] = f"At most {MAX_DESCRIPTION} characters"
    if problems:
        raise NextronError(422, ErrorCode.VALIDATION_ERROR, "The upload form failed validation", problems)
    return EvidenceService.AcquisitionContext(source_type, method, description, received_at)


def _ensure_case_accepts_evidence(factory: sessionmaker[Session], case_id: uuid.UUID) -> None:
    with factory() as session:
        Lifecycle.ensure_writable(get_case(session, case_id))


def _preserve(factory, storage, case_id, upload, media, context, actor, settings: Settings):
    queued: dict = {}

    def queue_analysis(session: Session, evidence) -> None:
        job = JobService.enqueue(session, job_type=JobType.INVESTIGATION_RUN, case_id=case_id, evidence_id=evidence.id,
                                 requested_by=actor, settings=settings, parameters={"trigger": "upload"})
        queued["job"] = JobReference(job_id=job.id, job_number=job.display_number, state=job.state)

    with factory() as session:
        evidence, duplicates = EvidenceService.preserve(
            session, storage, case_id=case_id, upload=upload, media=media, context=context, actor=actor,
            before_commit=queue_analysis if Preferences.auto_analyze(session, settings) else None,
        )
        return evidence, [DuplicateReference(evidence_id=d.id, evidence_number=d.display_number) for d in duplicates], queued.get("job")


async def acquire_upload(
    request: Request,
    case_id: uuid.UUID,
    *,
    settings: Settings,
    storage: LocalStorage,
    session_factory: sessionmaker[Session],
    actor: str,
) -> UploadedEvidence:
    await run_in_threadpool(_ensure_case_accepts_evidence, session_factory, case_id)

    received_at = datetime.now(timezone.utc)
    staged_path = storage.new_staging_path()
    try:
        upload = await receive_upload(
            request, staged_path, max_file_bytes=settings.MAX_UPLOAD_SIZE_BYTES, file_field=FILE_FIELD, text_fields=TEXT_FIELDS
        )
        context = _context(upload, received_at)
        media = await run_in_threadpool(
            identify_media, staged_path, ffprobe=settings.FFPROBE_PATH, timeout_seconds=settings.MEDIA_PROBE_TIMEOUT_SECONDS
        )
        evidence, duplicates, job = await run_in_threadpool(
            _preserve, session_factory, storage, case_id, upload, media, context, actor, settings
        )
    finally:
        storage.discard_staging(staged_path)  # no-op once promoted; removes rejected or partial uploads

    return UploadedEvidence(**EvidenceRead.of(evidence).model_dump(), duplicates_in_case=duplicates, analysis_job=job)
