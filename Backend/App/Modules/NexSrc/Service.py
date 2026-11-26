"""NEX-SRC Source Intelligence service: add a source URL to a case, retrieve it as a background job, record history.

Adding or refreshing a source queues a SOURCE_RESOLUTION job; a worker runs `run_retrieval`. Retrieved media is not
analysed in place: it goes through NEX-CAP validation and NEX-EVD preservation like an upload (source_type
SOURCE_RETRIEVAL), gets its own evidence record and custody events, and its investigation run is queued with it.
Every attempt, whatever the outcome, appends a source_observations row and bumps the record's revision.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from Backend.App.Config import Settings
from Backend.App.Contracts.ExecutionStates import JobState, JobType
from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Modules.NexCap.FileAcquisition import ReceivedUpload, safe_display_filename
from Backend.App.Modules.NexCap.Validation import identify_media
from Backend.App.Modules.NexCm import Lifecycle
from Backend.App.Modules.NexCm.Service import get_case
from Backend.App.Modules.NexEvd import Service as EvidenceService
from Backend.App.Modules.NexSrc import Connectors, SafeFetch
from Backend.App.Realtime import Outbox
from Backend.App.Services import Preferences
from Backend.App.Storage.LocalStorage import LocalStorage
from Backend.App.Workers import JobService
from Database.PostgreSQL.Models import AnalysisJob, SourceObservation, SourceRecord


def _event(session: Session, source: SourceRecord, suffix: str, **payload) -> None:
    Outbox.publish(session, f"source.{suffix}", aggregate_type="source", aggregate_id=source.id, case_id=source.case_id,
                   payload={"source_number": source.display_number, "state": source.state, "platform": source.platform,
                            "revision": source.revision, "evidence_id": str(source.evidence_id) if source.evidence_id else None} | payload)


def get_source(session: Session, source_id: uuid.UUID, *, for_update: bool = False) -> SourceRecord:
    query = select(SourceRecord).where(SourceRecord.id == source_id)
    source = session.scalars(query.with_for_update() if for_update else query).first()
    if source is None:
        raise NextronError(404, ErrorCode.SOURCE_NOT_FOUND, "The requested source does not exist")
    return source


def _queue(session: Session, source: SourceRecord, actor: str, settings: Settings) -> AnalysisJob:
    return JobService.enqueue(session, job_type=JobType.SOURCE_RESOLUTION, case_id=source.case_id, requested_by=actor,
                              settings=settings, parameters={"source_id": str(source.id)})


def add_source(session: Session, case_id: uuid.UUID, url: str, actor: str, settings: Settings, notes: str | None = None) -> tuple[SourceRecord, AnalysisJob]:
    Lifecycle.ensure_writable(get_case(session, case_id, for_update=True))
    try:
        normalized = SafeFetch.normalize(url)
    except SafeFetch.Refused as exc:
        raise NextronError(422, ErrorCode.INVALID_SOURCE_URL, str(exc)) from exc
    source = SourceRecord(case_id=case_id, url=url.strip(), normalized_url=normalized, platform=Connectors.platform_of(normalized),
                          state="PENDING", revision=1, created_by=actor, notes=(notes or "").strip() or None)
    session.add(source)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        existing = session.scalars(select(SourceRecord).where(SourceRecord.case_id == case_id, SourceRecord.normalized_url == normalized)).first()
        raise NextronError(409, ErrorCode.SOURCE_EXISTS, "This URL is already a source in this case",
                           {"source_id": str(existing.id) if existing else None}) from exc
    job = _queue(session, source, actor, settings)
    _event(session, source, "created", url=normalized, job_id=str(job.id))
    session.commit()
    return source, job


def refresh(session: Session, source_id: uuid.UUID, actor: str, settings: Settings) -> tuple[SourceRecord, AnalysisJob]:
    source = get_source(session, source_id, for_update=True)
    Lifecycle.ensure_writable(get_case(session, source.case_id))
    active = session.scalar(select(func.count()).select_from(AnalysisJob).where(
        AnalysisJob.job_type == JobType.SOURCE_RESOLUTION.value, AnalysisJob.state.in_(("QUEUED", "RUNNING")),
        AnalysisJob.parameters["source_id"].astext == str(source.id)))
    if active:
        raise NextronError(409, ErrorCode.SOURCE_BUSY, "A retrieval of this source is already queued or running")
    job = _queue(session, source, actor, settings)
    _event(session, source, "refresh_requested", job_id=str(job.id))
    session.commit()
    return source, job


def history(session: Session, source_id: uuid.UUID) -> list[SourceObservation]:
    get_source(session, source_id)
    return list(session.scalars(select(SourceObservation).where(SourceObservation.source_id == source_id).order_by(SourceObservation.revision)))


def list_sources(session: Session, *, case_id: uuid.UUID | None, page: int, page_size: int) -> tuple[list[SourceRecord], int]:
    conditions = [SourceRecord.case_id == case_id] if case_id else []
    total = session.scalar(select(func.count()).select_from(SourceRecord).where(*conditions)) or 0
    rows = session.scalars(select(SourceRecord).where(*conditions).order_by(SourceRecord.source_number.desc())
                           .offset((page - 1) * page_size).limit(page_size))
    return list(rows), total


# ── the worker side ──────────────────────────────────────────────────────────────────────────

def run_retrieval(factory: sessionmaker[Session], storage: LocalStorage, settings: Settings, job_id: uuid.UUID, worker_id: str,
                  *, allow: frozenset[str] = frozenset()) -> JobState | None:
    """Retrieve the job's source and record the outcome. Returns the job's end state, or None if the lease was lost."""
    with factory() as session:
        job = JobService.get_job(session, job_id)
        source = get_source(session, uuid.UUID(job.parameters["source_id"]))
        normalized, case_id, source_ref = source.normalized_url, source.case_id, source.id
        session.commit()

    staged = storage.new_staging_path()
    retrieval = Connectors.retrieve(normalized, staged, max_bytes=settings.MAX_UPLOAD_SIZE_BYTES,
                                    timeout=min(settings.MODULE_TIMEOUT_SECONDS, 120.0), allow=allow)
    evidence = None
    try:
        if retrieval.outcome == "RETRIEVED":
            evidence, problem = _preserve(factory, storage, settings, case_id, normalized, retrieval, job_id)
            if problem:
                retrieval.outcome, retrieval.detail = "METADATA_ONLY", problem
    finally:
        storage.discard_staging(staged)  # no-op once promoted

    with factory() as session:
        if not JobService.fence(session, job_id, worker_id):
            session.rollback()
            return None
        source = get_source(session, source_ref, for_update=True)
        source.revision = source.revision + (0 if source.state == "PENDING" and source.last_retrieved_at is None else 1)
        meta = retrieval.metadata or {}
        session.add(SourceObservation(
            source_id=source.id, revision=source.revision, job_id=job_id, connector=retrieval.connector, outcome=retrieval.outcome,
            detail=retrieval.detail, requested_url=normalized, final_url=retrieval.final_url, redirects=retrieval.hops,
            http_status=retrieval.http_status, content_type=retrieval.content_type, bytes_received=retrieval.bytes_received,
            media_sha256=retrieval.media_sha256 if evidence else None, evidence_id=evidence.id if evidence else None,
            metadata_={k: v for k, v in (meta | {"media_url": retrieval.media_url}).items() if v},
        ))
        source.state, source.state_detail = retrieval.outcome, retrieval.detail
        source.title = meta.get("title") or source.title
        source.claimed_publication_time = meta.get("claimed_publication_time") or source.claimed_publication_time
        if evidence is not None:
            source.evidence_id = evidence.id
        source.last_retrieved_at = source.updated_at = datetime.now(timezone.utc)
        session.flush()
        _event(session, source, "retrieved" if retrieval.outcome == "RETRIEVED" else "retrieval_ended", outcome=retrieval.outcome,
               detail=retrieval.detail, job_id=str(job_id))
        session.commit()
        job = JobService.get_job(session, job_id)
        state = JobState.FAILED if retrieval.outcome == "FAILED" else JobState.COMPLETED
        progress = {"planned": 1, "finished": 1, "by_state": {retrieval.outcome: 1}, "current": None}
        if not JobService.finish(session, job, worker_id, state, progress=progress,
                                 error={"code": retrieval.outcome, "message": retrieval.detail} if state is JobState.FAILED else None):
            return None
        return state


def _preserve(factory, storage, settings: Settings, case_id: uuid.UUID, url: str, retrieval: Connectors.Retrieval, job_id: uuid.UUID):
    """Validate and preserve retrieved media as evidence (and queue its run). Returns (evidence, problem)."""
    try:
        media = identify_media(retrieval.media_path, ffprobe=settings.FFPROBE_PATH, timeout_seconds=settings.MEDIA_PROBE_TIMEOUT_SECONDS)
    except NextronError as exc:
        return None, f"Retrieved {retrieval.media_size} bytes, but they are not valid media: {exc.message}"
    name = safe_display_filename((retrieval.media_url or url).rstrip("/").rsplit("/", 1)[-1].split("?", 1)[0])
    upload = ReceivedUpload(staged_path=retrieval.media_path, filename=name, declared_content_type=retrieval.content_type,
                            size_bytes=retrieval.media_size, sha256=retrieval.media_sha256, fields={})
    context = EvidenceService.AcquisitionContext("SOURCE_RETRIEVAL", "CONNECTOR_RETRIEVAL", f"Retrieved from {retrieval.media_url or url}",
                                                 datetime.now(timezone.utc))

    def queue_run(session: Session, evidence) -> None:
        if Preferences.auto_analyze(session, settings):
            JobService.enqueue(session, job_type=JobType.INVESTIGATION_RUN, case_id=case_id, evidence_id=evidence.id,
                               requested_by=settings.OPERATOR_NAME, settings=settings, parameters={"trigger": "source", "source_job": str(job_id)})

    with factory() as session:
        try:
            evidence, _ = EvidenceService.preserve(session, storage, case_id=case_id, upload=upload, media=media, context=context,
                                                   actor=settings.OPERATOR_NAME, before_commit=queue_run)
        except NextronError as exc:
            return None, f"The retrieved media could not be preserved: {exc.message}"
    return evidence, None
