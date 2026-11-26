"""The Job Service: the only code that changes a job's state (plan decision D-7).

Lifecycle:  QUEUED --claim--> RUNNING --finish--> COMPLETED | PARTIALLY_COMPLETED | FAILED | CANCELLED
                               |  \\--fail_or_retry / lease expiry--> QUEUED (after a backoff) or FAILED
                               \\--cancel requested: the runner stops between modules --> CANCELLED

* Claiming uses `FOR UPDATE SKIP LOCKED`, so two workers never claim the same job.
* A claimed job carries a lease (owner + expiry). The worker renews it with heartbeats. Every write a worker
  makes for a job is fenced on `lease_owner = me AND state = 'RUNNING'`: a worker that lost its lease (it
  stalled and another worker took over) cannot write anything more for that job.
* `recover_expired` finds RUNNING jobs whose lease ran out (the worker crashed), records the interrupted
  module executions as FAILED / LEASE_EXPIRED, and requeues the job with backoff, or fails it once the
  attempts are used up.

Functions that take a session and say "commits" own their transaction; the others only add to the caller's.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from Backend.App.Config import Settings
from Backend.App.Contracts.ExecutionStates import FailureReason, JobState, JobType
from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Realtime import Outbox
from Database.PostgreSQL.Models import AnalysisExecution, AnalysisJob

TERMINAL = {s.value for s in JobState if s.terminal}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _event(session: Session, job: AnalysisJob, suffix: str, **payload: Any) -> None:
    Outbox.publish(
        session, f"job.{suffix}", aggregate_type="job", aggregate_id=job.id, case_id=job.case_id, job_id=job.id,
        payload={"job_number": job.display_number, "job_type": job.job_type, "state": job.state,
                 "evidence_id": str(job.evidence_id) if job.evidence_id else None, "attempt": job.attempt} | payload,
    )


# ── creating and reading ─────────────────────────────────────────────────────────────────────

def enqueue(
    session: Session,
    *,
    job_type: JobType,
    case_id: uuid.UUID,
    requested_by: str,
    settings: Settings,
    evidence_id: uuid.UUID | None = None,
    parameters: dict[str, Any] | None = None,
    priority: int = 50,
) -> AnalysisJob:
    """Adds a QUEUED job and its job.queued event to the caller's transaction (does not commit)."""
    job = AnalysisJob(
        job_type=job_type.value,
        case_id=case_id,
        evidence_id=evidence_id,
        state=JobState.QUEUED.value,
        priority=priority,
        requested_by=requested_by,
        parameters=parameters or {},
        attempt=0,
        max_attempts=settings.JOB_MAX_ATTEMPTS,
        timeout_seconds=settings.JOB_TIMEOUT_SECONDS,
        available_at=_now(),
        cancel_requested=False,
    )
    session.add(job)
    session.flush()  # assigns job_number
    _event(session, job, "queued")
    return job


def get_job(session: Session, job_id: uuid.UUID, *, for_update: bool = False) -> AnalysisJob:
    query = select(AnalysisJob).where(AnalysisJob.id == job_id)
    if for_update:
        query = query.with_for_update()
    job = session.scalars(query).first()
    if job is None:
        raise NextronError(404, ErrorCode.JOB_NOT_FOUND, "The requested job does not exist")
    return job


# ── claiming and leases ──────────────────────────────────────────────────────────────────────

_CLAIM = text("""
    UPDATE analysis_jobs
       SET state = 'RUNNING',
           lease_owner = :worker,
           lease_expires_at = now() + make_interval(secs => :lease),
           heartbeat_at = now(),
           attempt = attempt + 1,
           started_at = COALESCE(started_at, now()),
           updated_at = now()
     WHERE id = (
            SELECT id FROM analysis_jobs
             WHERE state = 'QUEUED' AND available_at <= now() AND attempt < max_attempts
             ORDER BY priority DESC, available_at, job_number
             FOR UPDATE SKIP LOCKED
             LIMIT 1)
 RETURNING id
""")


def claim(session: Session, worker_id: str, *, lease_seconds: int) -> AnalysisJob | None:
    """Claims the next runnable job for this worker, or returns None. Commits."""
    job_id = session.execute(_CLAIM, {"worker": worker_id, "lease": lease_seconds}).scalar()
    if job_id is None:
        session.rollback()
        return None
    job = session.get(AnalysisJob, job_id, populate_existing=True)
    _event(session, job, "started", worker_id=worker_id)
    session.commit()
    return job


@dataclass(frozen=True)
class Heartbeat:
    lease_held: bool
    cancel_requested: bool


def heartbeat(session: Session, job_id: uuid.UUID, worker_id: str, *, lease_seconds: int) -> Heartbeat:
    """Renews the lease. `lease_held=False` means another worker or the recovery took the job over. Commits."""
    row = session.execute(
        text("""UPDATE analysis_jobs SET lease_expires_at = now() + make_interval(secs => :lease), heartbeat_at = now()
                 WHERE id = :id AND lease_owner = :worker AND state = 'RUNNING'
             RETURNING cancel_requested"""),
        {"id": job_id, "worker": worker_id, "lease": lease_seconds},
    ).first()
    session.commit()
    return Heartbeat(lease_held=row is not None, cancel_requested=bool(row and row[0]))


def fence(session: Session, job_id: uuid.UUID, worker_id: str, **values: Any) -> bool:
    """Locks the job row for the caller's transaction if this worker still holds its lease, applying `values`.

    Every runner transaction starts with this, so a worker whose lease expired cannot write results.
    """
    statement = (
        update(AnalysisJob)
        .where(AnalysisJob.id == job_id, AnalysisJob.lease_owner == worker_id, AnalysisJob.state == JobState.RUNNING.value)
        .values(updated_at=_now(), **values)
        .returning(AnalysisJob.id)
    )
    return session.execute(statement).first() is not None


def finish(
    session: Session,
    job: AnalysisJob,
    worker_id: str,
    state: JobState,
    *,
    plan: dict | None = None,
    progress: dict | None = None,
    error: dict | None = None,
) -> bool:
    """Ends a RUNNING job this worker holds. Returns False (and writes nothing) if the lease was lost. Commits."""
    assert state.terminal
    values: dict[str, Any] = dict(state=state.value, lease_owner=None, lease_expires_at=None, finished_at=_now(), error=error)
    if plan is not None:
        values["plan"] = plan
    if progress is not None:
        values["progress"] = progress
    if not fence(session, job.id, worker_id, **values):
        session.rollback()
        return False
    session.refresh(job)
    _event(session, job, state.value.lower(), progress=progress or job.progress, error=error)
    session.commit()
    return True


def _backoff(settings: Settings, attempt: int) -> timedelta:
    return timedelta(seconds=settings.JOB_RETRY_BASE_SECONDS * (2 ** max(attempt - 1, 0)))


def _requeue_or_fail(session: Session, job: AnalysisJob, error: dict, settings: Settings) -> None:
    """For a locked RUNNING job: back to QUEUED after a backoff, or FAILED when no attempt is left."""
    if job.cancel_requested:
        job.state, job.finished_at = JobState.CANCELLED.value, _now()
    elif job.attempt < job.max_attempts:
        job.state = JobState.QUEUED.value
        job.available_at = _now() + _backoff(settings, job.attempt)
    else:
        job.state, job.finished_at = JobState.FAILED.value, _now()
    job.lease_owner = job.lease_expires_at = None
    job.error = error
    job.updated_at = _now()
    session.flush()
    if job.state == JobState.QUEUED.value:
        _event(session, job, "retry_scheduled", error=error, available_at=job.available_at.isoformat())
    else:
        _event(session, job, job.state.lower(), error=error)


def fail_or_retry(session: Session, job: AnalysisJob, worker_id: str, error: dict, settings: Settings) -> bool:
    """The runner hit an infrastructure error (not a module failure). Commits; False if the lease was lost."""
    session.rollback()
    if not fence(session, job.id, worker_id):
        session.rollback()
        return False
    session.refresh(job)
    _requeue_or_fail(session, job, error, settings)
    session.commit()
    return True


def recover_expired(session: Session, settings: Settings, *, close_execution) -> list[uuid.UUID]:
    """Recovers RUNNING jobs whose lease expired. `close_execution(session, job, execution, reason, detail)` records
    an interrupted execution as FAILED (T-MIR supplies it, so its result envelope is written the usual way). Commits."""
    jobs = list(session.scalars(
        select(AnalysisJob)
        .where(AnalysisJob.state == JobState.RUNNING.value, AnalysisJob.lease_expires_at < _now())
        .with_for_update(skip_locked=True)
    ))
    for job in jobs:
        owner = job.lease_owner
        interrupted = session.scalars(
            select(AnalysisExecution).where(AnalysisExecution.job_id == job.id, AnalysisExecution.state == "RUNNING")
        ).all()
        for execution in interrupted:
            close_execution(session, job, execution, FailureReason.LEASE_EXPIRED,
                            f"Worker {owner} stopped renewing its lease while this module was running")
        _requeue_or_fail(session, job, {"code": FailureReason.LEASE_EXPIRED.value,
                                        "message": f"Worker {owner} stopped renewing its lease", "worker_id": owner}, settings)
    session.commit()
    return [job.id for job in jobs]


# ── operator actions ─────────────────────────────────────────────────────────────────────────

def request_cancel(session: Session, job_id: uuid.UUID, actor: str) -> AnalysisJob:
    """A queued job is cancelled at once; a running job is flagged and stops before its next module. Commits."""
    job = get_job(session, job_id, for_update=True)
    if job.state in TERMINAL:
        raise NextronError(409, ErrorCode.JOB_NOT_CANCELLABLE, f"The job has already ended ({job.state})")
    if job.state == JobState.QUEUED.value:
        job.state, job.finished_at, job.cancel_requested = JobState.CANCELLED.value, _now(), True
        job.updated_at = _now()
        session.flush()
        _event(session, job, "cancelled", requested_by=actor)
    elif not job.cancel_requested:
        job.cancel_requested = True
        job.updated_at = _now()
        session.flush()
        _event(session, job, "cancel_requested", requested_by=actor)
    session.commit()
    session.refresh(job)
    return job


def retry(session: Session, job_id: uuid.UUID, actor: str, settings: Settings) -> AnalysisJob:
    """A new job with the same request. Work that already completed on identical inputs is reused, not redone. Commits."""
    old = get_job(session, job_id)
    if old.state not in (JobState.FAILED.value, JobState.PARTIALLY_COMPLETED.value, JobState.CANCELLED.value):
        raise NextronError(409, ErrorCode.JOB_NOT_RETRYABLE, f"Only failed, partial or cancelled jobs can be retried (this one is {old.state})")
    job = enqueue(
        session, job_type=JobType(old.job_type), case_id=old.case_id, evidence_id=old.evidence_id, requested_by=actor,
        settings=settings, parameters=old.parameters | {"retry_of": str(old.id)}, priority=old.priority,
    )
    session.commit()
    session.refresh(job)
    return job
