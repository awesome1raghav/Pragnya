"""Job APIs (Job Service): list, inspect, cancel and retry durable background jobs."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from Backend.App.Config import Settings
from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Dependencies import get_actor, get_db_session, get_settings_dependency
from Backend.App.Orchestration.TMir import Service as TMirService
from Backend.App.Orchestration.TMir.Schemas import JobRead
from Backend.App.Schemas.Common import ErrorEnvelope, SuccessEnvelope, envelope
from Backend.App.Schemas.Pagination import MAX_PAGE_SIZE, PaginatedEnvelope, paginated
from Backend.App.Workers import JobService
from Database.PostgreSQL.Models.AnalysisJob import JOB_STATES, JOB_TYPES

router = APIRouter(tags=["Jobs"])

_JOB_404 = {404: {"model": ErrorEnvelope, "description": "JOB_NOT_FOUND"}}


@router.get("/jobs", response_model=PaginatedEnvelope[JobRead], summary="List jobs, newest first")
def list_jobs(
    state: str | None = Query(default=None, description=", ".join(JOB_STATES)),
    active: bool | None = Query(default=None, description="true: only QUEUED and RUNNING"),
    job_type: str | None = Query(default=None, description=", ".join(JOB_TYPES)),
    case_id: uuid.UUID | None = None,
    evidence_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    session: Session = Depends(get_db_session),
):
    if state is not None and state not in JOB_STATES:
        raise NextronError(422, ErrorCode.VALIDATION_ERROR, "Unknown job state", {"allowed": list(JOB_STATES)})
    if job_type is not None and job_type not in JOB_TYPES:
        raise NextronError(422, ErrorCode.VALIDATION_ERROR, "Unknown job type", {"allowed": list(JOB_TYPES)})
    items, total = TMirService.list_jobs(session, page=page, page_size=page_size, state=state, active=active, case_id=case_id,
                                         evidence_id=evidence_id, job_type=job_type)
    return paginated(items, "Jobs retrieved successfully", page=page, page_size=page_size, total_items=total)


@router.get("/jobs/{job_id}", response_model=SuccessEnvelope[JobRead], responses=_JOB_404, summary="Job detail")
def job_detail(job_id: uuid.UUID, session: Session = Depends(get_db_session)):
    return envelope(TMirService.job_read(session, job_id), "Job retrieved successfully")


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=SuccessEnvelope[JobRead],
    responses=_JOB_404 | {409: {"model": ErrorEnvelope, "description": "JOB_NOT_CANCELLABLE"}},
    summary="Cancel a job (queued: at once; running: before its next module)",
)
def cancel_job(job_id: uuid.UUID, session: Session = Depends(get_db_session), actor: str = Depends(get_actor)):
    job = JobService.request_cancel(session, job_id, actor)
    message = "Job cancelled" if job.state == "CANCELLED" else "Cancellation requested; the job stops before its next module"
    return envelope(TMirService.job_read(session, job.id), message)


@router.post(
    "/jobs/{job_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SuccessEnvelope[JobRead],
    responses=_JOB_404 | {409: {"model": ErrorEnvelope, "description": "JOB_NOT_RETRYABLE"}},
    summary="Queue a new job with the same request; completed work on identical inputs is reused",
)
def retry_job(
    job_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    actor: str = Depends(get_actor),
    settings: Settings = Depends(get_settings_dependency),
):
    job = JobService.retry(session, job_id, actor, settings)
    return envelope(TMirService.job_read(session, job.id), f"Queued {job.display_number}")
