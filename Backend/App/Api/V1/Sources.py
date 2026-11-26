"""Source APIs (NEX-SRC): add a URL to a case (retrieved by a worker), list, inspect, refresh, history, connectors."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from Backend.App.Config import Settings
from Backend.App.Dependencies import get_actor, get_db_session, get_settings_dependency
from Backend.App.Modules.NexCm.Service import get_case
from Backend.App.Modules.NexSrc import Service as SourceService
from Backend.App.Schemas.Common import ErrorEnvelope, SuccessEnvelope, envelope
from Backend.App.Schemas.Pagination import MAX_PAGE_SIZE, PaginatedEnvelope, paginated
from Database.PostgreSQL.Models import SourceObservation, SourceRecord

router = APIRouter(tags=["Sources (NEX-SRC)"])


class SourceCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2048, examples=["https://example.org/news/harbour-fire"])
    notes: str | None = Field(default=None, max_length=2000)


class SourceRead(BaseModel):
    source_id: uuid.UUID
    source_number: str
    case_id: uuid.UUID
    url: str
    normalized_url: str
    platform: str
    state: str
    state_detail: str | None
    revision: int
    title: str | None
    claimed_publication_time: str | None = Field(description="As the source states it; not verified, not NEXTRON's time")
    evidence_id: uuid.UUID | None
    notes: str | None
    created_by: str
    created_at: datetime
    last_retrieved_at: datetime | None
    job_id: uuid.UUID | None = None

    @classmethod
    def of(cls, s: SourceRecord, job_id: uuid.UUID | None = None) -> "SourceRead":
        return cls(source_id=s.id, source_number=s.display_number, case_id=s.case_id, url=s.url, normalized_url=s.normalized_url,
                   platform=s.platform, state=s.state, state_detail=s.state_detail, revision=s.revision, title=s.title,
                   claimed_publication_time=s.claimed_publication_time, evidence_id=s.evidence_id, notes=s.notes, created_by=s.created_by,
                   created_at=s.created_at, last_retrieved_at=s.last_retrieved_at, job_id=job_id)


class ObservationRead(BaseModel):
    revision: int
    connector: str
    outcome: str
    detail: str | None
    requested_url: str
    final_url: str | None
    redirects: list[dict]
    http_status: int | None
    content_type: str | None
    bytes_received: int | None
    media_sha256: str | None
    evidence_id: uuid.UUID | None
    metadata: dict
    retrieved_at: datetime

    @classmethod
    def of(cls, o: SourceObservation) -> "ObservationRead":
        return cls(revision=o.revision, connector=o.connector, outcome=o.outcome, detail=o.detail, requested_url=o.requested_url,
                   final_url=o.final_url, redirects=o.redirects or [], http_status=o.http_status, content_type=o.content_type,
                   bytes_received=o.bytes_received, media_sha256=o.media_sha256, evidence_id=o.evidence_id, metadata=o.metadata_ or {},
                   retrieved_at=o.retrieved_at)


_SOURCE_404 = {404: {"model": ErrorEnvelope, "description": "SOURCE_NOT_FOUND"}}


@router.post("/cases/{case_id}/sources", status_code=status.HTTP_202_ACCEPTED, response_model=SuccessEnvelope[SourceRead],
             responses={404: {"model": ErrorEnvelope}, 409: {"model": ErrorEnvelope, "description": "SOURCE_EXISTS or CASE_ARCHIVED"},
                        422: {"model": ErrorEnvelope, "description": "INVALID_SOURCE_URL"}},
             summary="Add a source URL; a worker retrieves it")
def add_source(case_id: uuid.UUID, body: SourceCreate, session: Session = Depends(get_db_session), actor: str = Depends(get_actor),
               settings: Settings = Depends(get_settings_dependency)):
    source, job = SourceService.add_source(session, case_id, body.url, actor, settings, body.notes)
    return envelope(SourceRead.of(source, job.id), f"{source.display_number} added; retrieval queued as {job.display_number}")


@router.get("/cases/{case_id}/sources", response_model=PaginatedEnvelope[SourceRead], summary="A case's sources")
def case_sources(case_id: uuid.UUID, page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
                 session: Session = Depends(get_db_session)):
    get_case(session, case_id)
    rows, total = SourceService.list_sources(session, case_id=case_id, page=page, page_size=page_size)
    return paginated([SourceRead.of(s) for s in rows], "Sources retrieved successfully", page=page, page_size=page_size, total_items=total)


@router.get("/sources", response_model=PaginatedEnvelope[SourceRead], summary="Sources across investigations")
def all_sources(case_id: uuid.UUID | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
                session: Session = Depends(get_db_session)):
    rows, total = SourceService.list_sources(session, case_id=case_id, page=page, page_size=page_size)
    return paginated([SourceRead.of(s) for s in rows], "Sources retrieved successfully", page=page, page_size=page_size, total_items=total)


@router.get("/sources/connectors", response_model=SuccessEnvelope[list[dict]], summary="What each connector can retrieve")
def connectors():
    return envelope([
        {"connector": "generic", "available": True, "covers": "Public http(s) pages and direct media links",
         "retrieves": "Direct media, or the media a page declares (Open Graph / Twitter card); page title and claimed publication time"},
        *[{"connector": p.lower(), "available": False, "covers": p.title(),
           "retrieves": "Nothing: needs an approved platform API connector and credentials, which are not configured"}
          for p in ("YOUTUBE", "X", "INSTAGRAM", "FACEBOOK", "TIKTOK", "WHATSAPP")],
    ], "Connectors retrieved successfully")


@router.get("/sources/{source_id}", response_model=SuccessEnvelope[SourceRead], responses=_SOURCE_404, summary="Source detail")
def source_detail(source_id: uuid.UUID, session: Session = Depends(get_db_session)):
    return envelope(SourceRead.of(SourceService.get_source(session, source_id)), "Source retrieved successfully")


@router.post("/sources/{source_id}/refresh", status_code=status.HTTP_202_ACCEPTED, response_model=SuccessEnvelope[SourceRead],
             responses=_SOURCE_404 | {409: {"model": ErrorEnvelope, "description": "SOURCE_BUSY"}}, summary="Retrieve the source again")
def refresh_source(source_id: uuid.UUID, session: Session = Depends(get_db_session), actor: str = Depends(get_actor),
                   settings: Settings = Depends(get_settings_dependency)):
    source, job = SourceService.refresh(session, source_id, actor, settings)
    return envelope(SourceRead.of(source, job.id), f"Retrieval queued as {job.display_number}")


@router.get("/sources/{source_id}/history", response_model=SuccessEnvelope[list[ObservationRead]], responses=_SOURCE_404,
            summary="Every retrieval attempt, with each redirect hop and the address it resolved to")
def source_history(source_id: uuid.UUID, session: Session = Depends(get_db_session)):
    return envelope([ObservationRead.of(o) for o in SourceService.history(session, source_id)], "History retrieved successfully")
