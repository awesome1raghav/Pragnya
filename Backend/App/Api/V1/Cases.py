"""NEX-CM routes: /cases."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Dependencies import get_actor, get_db_session
from Backend.App.Modules.NexCm import Service
from Backend.App.Modules.NexCm.Schemas import (
    ArchiveRequest,
    CaseCreate,
    CaseEvidenceStatistics,
    CasePriority,
    CaseRead,
    CaseStatistics,
    CaseStatus,
    CaseSummary,
    CaseUpdate,
)
from Backend.App.Schemas.Common import ErrorEnvelope, SuccessEnvelope, envelope
from Backend.App.Schemas.Events import EventPageEnvelope, event_page
from Backend.App.Schemas.Pagination import MAX_PAGE_SIZE, PaginatedEnvelope, paginated
from Database.PostgreSQL.Repositories import EventRepository
from Database.PostgreSQL.Repositories.CaseRepository import SORTABLE, CaseFilters

router = APIRouter(prefix="/cases", tags=["Cases (NEX-CM)"])

_NOT_FOUND = {404: {"model": ErrorEnvelope, "description": "CASE_NOT_FOUND"}}
_CONFLICT = {409: {"model": ErrorEnvelope, "description": "Lifecycle conflict"}}


def _split(values: list[str] | None) -> tuple[str, ...]:
    """Accept both ?status=A&status=B and ?status=A,B."""
    return tuple(part.strip() for value in values or [] for part in value.split(",") if part.strip())


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SuccessEnvelope[CaseRead], summary="Create case")
def create_case(body: CaseCreate, session: Session = Depends(get_db_session), actor: str = Depends(get_actor)):
    return envelope(Service.create_case(session, body, actor), "Investigation created successfully")


@router.get("", response_model=PaginatedEnvelope[CaseRead], summary="List cases")
def list_cases(
    search: str | None = Query(default=None, max_length=200, description="Title, description or case number"),
    status_filter: list[str] | None = Query(default=None, alias="status", description="One or more statuses; ARCHIVED cases appear only when requested"),
    priority: list[str] | None = Query(default=None),
    created_from: datetime | None = Query(default=None, alias="from"),
    created_to: datetime | None = Query(default=None, alias="to"),
    sort_by: Literal[tuple(SORTABLE)] = "created_at",  # type: ignore[valid-type]
    sort_order: Literal["asc", "desc"] = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    session: Session = Depends(get_db_session),
):
    statuses, priorities = _split(status_filter), _split(priority)
    invalid = [s for s in statuses if s not in CaseStatus.__args__] + [p for p in priorities if p not in CasePriority.__args__]
    if invalid:
        raise NextronError(422, ErrorCode.VALIDATION_ERROR, "Unknown status or priority filter", {"invalid": invalid})
    filters = CaseFilters(
        search=search or None,
        statuses=statuses,
        priorities=priorities,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    items, total = Service.list_cases(session, filters, page=page, page_size=page_size)
    return paginated(items, "Investigations retrieved successfully", page=page, page_size=page_size, total_items=total)


@router.get("/statistics", response_model=SuccessEnvelope[CaseStatistics], summary="Case statistics")
def statistics(session: Session = Depends(get_db_session)):
    return envelope(Service.overall_statistics(session), "Case statistics retrieved successfully")


@router.get("/{case_id}", response_model=SuccessEnvelope[CaseRead], responses=_NOT_FOUND, summary="Get case")
def get_case(case_id: uuid.UUID, session: Session = Depends(get_db_session)):
    return envelope(Service.read_case(session, Service.get_case(session, case_id)), "Investigation retrieved successfully")


@router.patch(
    "/{case_id}", response_model=SuccessEnvelope[CaseRead], responses=_NOT_FOUND | _CONFLICT, summary="Update case fields"
)
def update_case(case_id: uuid.UUID, body: CaseUpdate, session: Session = Depends(get_db_session), actor: str = Depends(get_actor)):
    return envelope(Service.update_case(session, case_id, body, actor), "Investigation updated successfully")


@router.post("/{case_id}/archive", response_model=SuccessEnvelope[CaseRead], responses=_NOT_FOUND | _CONFLICT, summary="Archive case")
def archive_case(
    case_id: uuid.UUID,
    body: ArchiveRequest | None = Body(default=None),
    session: Session = Depends(get_db_session),
    actor: str = Depends(get_actor),
):
    return envelope(Service.archive_case(session, case_id, body or ArchiveRequest(), actor), "Investigation archived successfully")


@router.post("/{case_id}/reopen", response_model=SuccessEnvelope[CaseRead], responses=_NOT_FOUND | _CONFLICT, summary="Reopen case")
def reopen_case(case_id: uuid.UUID, session: Session = Depends(get_db_session), actor: str = Depends(get_actor)):
    return envelope(Service.reopen_case(session, case_id, actor), "Investigation reopened successfully")


@router.get("/{case_id}/summary", response_model=SuccessEnvelope[CaseSummary], responses=_NOT_FOUND, summary="Case overview")
def case_summary(case_id: uuid.UUID, session: Session = Depends(get_db_session)):
    return envelope(Service.case_summary(session, case_id), "Investigation summary retrieved successfully")


@router.get(
    "/{case_id}/statistics", response_model=SuccessEnvelope[CaseEvidenceStatistics], responses=_NOT_FOUND, summary="Case counts"
)
def case_statistics(case_id: uuid.UUID, session: Session = Depends(get_db_session)):
    return envelope(Service.case_statistics(session, case_id), "Investigation statistics retrieved successfully")


@router.get("/{case_id}/events", response_model=EventPageEnvelope, responses=_NOT_FOUND, summary="Case events (cursor)")
def case_events(
    case_id: uuid.UUID,
    after: int = Query(default=0, ge=0, description="Return events with sequence greater than this"),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
):
    Service.get_case(session, case_id)
    events, has_more = EventRepository.page(session, case_id=case_id, after_sequence=after, limit=limit)
    return event_page(events, has_more, after=after, limit=limit, message="Investigation events retrieved successfully")
