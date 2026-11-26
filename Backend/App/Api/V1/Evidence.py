"""NEX-CAP / NEX-EVD / NEX-MET routes: upload, evidence records, integrity, preview, download, history."""

import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, sessionmaker

from Backend.App.Config import Settings
from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Dependencies import get_actor, get_db_session, get_session_factory, get_settings_dependency, get_storage
from Backend.App.Modules.NexCap import Service as AcquisitionService
from Backend.App.Modules.NexCm.Service import get_case
from Backend.App.Modules.NexEvd import ChainOfCustody, IntegrityService
from Backend.App.Modules.NexEvd.Schemas import (
    EvidenceListItem,
    EvidenceRead,
    EvidenceStatistics,
    IntegrityState,
    IntegrityVerification,
    UploadedEvidence,
)
from Backend.App.Modules.NexEvd.Service import get_evidence
from Backend.App.Modules.NexMet.Schemas import MetadataRead
from Backend.App.Schemas.Common import ErrorEnvelope, SuccessEnvelope, envelope
from Backend.App.Schemas.Events import EventPageEnvelope, event_page
from Backend.App.Schemas.Pagination import MAX_PAGE_SIZE, PaginatedEnvelope, paginated
from Backend.App.Storage.LocalStorage import LocalStorage
from Database.PostgreSQL.Models import Evidence
from Database.PostgreSQL.Models.Evidence import ACQUISITION_METHODS, MEDIA_TYPES, PRESERVATION_STATUSES, SOURCE_TYPES
from Database.PostgreSQL.Repositories import EventRepository, EvidenceRepository

router = APIRouter(tags=["Evidence (NEX-CAP / NEX-EVD / NEX-MET)"])

_EVIDENCE_404 = {404: {"model": ErrorEnvelope, "description": "EVIDENCE_NOT_FOUND"}}
_FILE_410 = {410: {"model": ErrorEnvelope, "description": "EVIDENCE_FILE_MISSING: the stored original is absent"}}

_UPLOAD_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["file"],
                    "properties": {
                        "file": {"type": "string", "format": "binary", "description": "One image, video or audio file"},
                        "source_type": {"type": "string", "enum": list(SOURCE_TYPES), "default": "USER_UPLOAD"},
                        "acquisition_method": {"type": "string", "enum": list(ACQUISITION_METHODS), "default": "DIRECT_UPLOAD"},
                        "description": {"type": "string", "maxLength": 2000},
                    },
                }
            }
        },
    }
}

# Inline previews are served as inert media: no sniffing, no scripts, no plugins.
_PREVIEW_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; img-src 'self'; media-src 'self'; style-src 'unsafe-inline'; sandbox",
    "Cache-Control": "private, max-age=0, must-revalidate",
}


@router.post(
    "/cases/{case_id}/evidence",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessEnvelope[UploadedEvidence],
    responses={
        400: {"model": ErrorEnvelope, "description": "INVALID_UPLOAD"},
        404: {"model": ErrorEnvelope, "description": "CASE_NOT_FOUND"},
        409: {"model": ErrorEnvelope, "description": "CASE_ARCHIVED"},
        413: {"model": ErrorEnvelope, "description": "UPLOAD_TOO_LARGE"},
        415: {"model": ErrorEnvelope, "description": "UNSUPPORTED_MEDIA_TYPE or INVALID_MEDIA_FORMAT"},
        503: {"model": ErrorEnvelope, "description": "STORAGE_UNAVAILABLE or MEDIA_PROBE_UNAVAILABLE"},
    },
    openapi_extra=_UPLOAD_BODY,
    summary="Upload evidence (streamed, hashed server-side, preserved)",
)
async def upload_evidence(
    case_id: uuid.UUID,
    request: Request,
    settings: Settings = Depends(get_settings_dependency),
    storage: LocalStorage = Depends(get_storage),
    session_factory: sessionmaker[Session] = Depends(get_session_factory),
    actor: str = Depends(get_actor),
):
    uploaded = await AcquisitionService.acquire_upload(
        request, case_id, settings=settings, storage=storage, session_factory=session_factory, actor=actor
    )
    return envelope(uploaded, "Evidence preserved successfully")


@router.get(
    "/cases/{case_id}/evidence",
    response_model=PaginatedEnvelope[EvidenceRead],
    responses={404: {"model": ErrorEnvelope, "description": "CASE_NOT_FOUND"}},
    summary="List a case's evidence",
)
def list_case_evidence(
    case_id: uuid.UUID,
    media_type: str | None = Query(default=None, description="IMAGE, VIDEO or AUDIO"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    session: Session = Depends(get_db_session),
):
    if media_type is not None and media_type not in MEDIA_TYPES:
        raise NextronError(422, ErrorCode.VALIDATION_ERROR, "Unknown media type", {"allowed": list(MEDIA_TYPES)})
    get_case(session, case_id)
    rows, total = EvidenceRepository.list_for_case(session, case_id, page=page, page_size=page_size, media_type=media_type)
    return paginated([EvidenceRead.of(e) for e in rows], "Evidence retrieved successfully", page=page, page_size=page_size, total_items=total)


@router.get("/evidence", response_model=PaginatedEnvelope[EvidenceListItem], summary="List evidence across investigations")
def list_all_evidence(
    case_id: uuid.UUID | None = Query(default=None, description="Limit to one investigation"),
    media_type: str | None = Query(default=None, description="IMAGE, VIDEO or AUDIO"),
    search: str | None = Query(default=None, max_length=200, description="Filename, evidence number or SHA-256 prefix"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    session: Session = Depends(get_db_session),
):
    if media_type is not None and media_type not in MEDIA_TYPES:
        raise NextronError(422, ErrorCode.VALIDATION_ERROR, "Unknown media type", {"allowed": list(MEDIA_TYPES)})
    if case_id is not None:
        get_case(session, case_id)
    rows, total = EvidenceRepository.list_all(
        session, page=page, page_size=page_size, case_id=case_id, media_type=media_type, text=(search or "").strip() or None
    )
    items = [EvidenceListItem.of_row(e, number, title) for e, number, title in rows]
    return paginated(items, "Evidence retrieved successfully", page=page, page_size=page_size, total_items=total)


@router.get("/evidence/statistics", response_model=SuccessEnvelope[EvidenceStatistics], summary="Evidence counts")
def evidence_statistics(session: Session = Depends(get_db_session)):
    by_media = {m: 0 for m in MEDIA_TYPES} | EvidenceRepository.counts_by(session, Evidence.media_type)
    by_status = {s: 0 for s in PRESERVATION_STATUSES} | EvidenceRepository.counts_by(session, Evidence.preservation_status)
    stats = EvidenceStatistics(
        total_evidence=sum(by_media.values()),
        by_media_type=by_media,
        by_preservation_status=by_status,
        total_bytes=EvidenceRepository.total_bytes(session),
    )
    return envelope(stats, "Evidence statistics retrieved successfully")


@router.get("/evidence/{evidence_id}", response_model=SuccessEnvelope[EvidenceRead], responses=_EVIDENCE_404, summary="Evidence detail")
def evidence_detail(evidence_id: uuid.UUID, session: Session = Depends(get_db_session)):
    return envelope(EvidenceRead.of(get_evidence(session, evidence_id)), "Evidence retrieved successfully")


@router.get(
    "/evidence/{evidence_id}/metadata",
    response_model=SuccessEnvelope[MetadataRead],
    responses=_EVIDENCE_404,
    summary="Latest extracted metadata",
)
def evidence_metadata(evidence_id: uuid.UUID, session: Session = Depends(get_db_session)):
    get_evidence(session, evidence_id)
    row = EvidenceRepository.latest_metadata(session, evidence_id)
    if row is None:
        raise NextronError(404, ErrorCode.METADATA_NOT_FOUND, "No metadata extraction has been recorded for this evidence")
    return envelope(MetadataRead.of(row, EvidenceRepository.metadata_versions(session, evidence_id)), "Metadata retrieved successfully")


@router.get(
    "/evidence/{evidence_id}/integrity",
    response_model=SuccessEnvelope[IntegrityState],
    responses=_EVIDENCE_404,
    summary="Recorded hash and last verification",
)
def evidence_integrity(evidence_id: uuid.UUID, session: Session = Depends(get_db_session)):
    evidence = get_evidence(session, evidence_id)
    return envelope(IntegrityService.state(session, evidence), "Integrity state retrieved successfully")


@router.post(
    "/evidence/{evidence_id}/verify-integrity",
    response_model=SuccessEnvelope[IntegrityVerification],
    responses=_EVIDENCE_404,
    summary="Recompute SHA-256 of the stored bytes and compare",
)
def verify_integrity(
    evidence_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    storage: LocalStorage = Depends(get_storage),
    actor: str = Depends(get_actor),
):
    evidence = get_evidence(session, evidence_id)
    result = IntegrityService.verify(session, storage, evidence, actor)
    messages = {
        "MATCH": "Stored bytes match the recorded SHA-256",
        "MISMATCH": "Stored bytes do NOT match the recorded SHA-256",
        "MISSING": "The stored original is missing",
    }
    return envelope(result, messages[result.result])


@router.get("/evidence/{evidence_id}/history", response_model=EventPageEnvelope, responses=_EVIDENCE_404, summary="Custody events (cursor)")
def evidence_history(
    evidence_id: uuid.UUID,
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
):
    get_evidence(session, evidence_id)
    events, has_more = EventRepository.page(session, evidence_id=evidence_id, after_sequence=after, limit=limit)
    return event_page(events, has_more, after=after, limit=limit, message="Evidence history retrieved successfully")


def _stored_path(storage: LocalStorage, evidence: Evidence):
    path = storage.local_path(evidence.storage_key)
    if path is None or not path.is_file():
        raise NextronError(410, ErrorCode.EVIDENCE_FILE_MISSING, "The preserved original is missing from storage; run an integrity check")
    return path


@router.get(
    "/evidence/{evidence_id}/preview",
    response_class=FileResponse,
    responses={200: {"description": "The original bytes, inline, with HTTP Range support"}} | _EVIDENCE_404 | _FILE_410,
    summary="Inline preview of the original bytes",
)
def evidence_preview(evidence_id: uuid.UUID, session: Session = Depends(get_db_session), storage: LocalStorage = Depends(get_storage)):
    evidence = get_evidence(session, evidence_id)
    return FileResponse(
        _stored_path(storage, evidence),
        media_type=evidence.mime_type,
        filename=evidence.original_filename,
        content_disposition_type="inline",
        headers=_PREVIEW_HEADERS | {"X-Evidence-SHA256": evidence.sha256},
    )


@router.get(
    "/evidence/{evidence_id}/download",
    response_class=FileResponse,
    responses={200: {"description": "The original bytes as an attachment"}} | _EVIDENCE_404 | _FILE_410,
    summary="Download the original bytes (recorded as a custody event)",
)
def evidence_download(
    evidence_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    storage: LocalStorage = Depends(get_storage),
    actor: str = Depends(get_actor),
):
    evidence = get_evidence(session, evidence_id)
    path = _stored_path(storage, evidence)
    ChainOfCustody.record(session, evidence, ChainOfCustody.DOWNLOADED, actor, {"sha256": evidence.sha256, "size_bytes": evidence.size_bytes})
    session.commit()
    return FileResponse(
        path,
        media_type=evidence.mime_type,
        filename=evidence.original_filename,
        headers={"X-Content-Type-Options": "nosniff", "X-Evidence-SHA256": evidence.sha256, "Cache-Control": "no-store"},
    )
