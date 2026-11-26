"""NEX-CM Case Management. Each write commits the case change and its event together."""

import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Backend.App.Modules.NexCm import Lifecycle
from Backend.App.Realtime import Outbox
from Backend.App.Modules.NexCm.Schemas import (
    ArchiveRequest,
    CaseCreate,
    CaseEvidenceStatistics,
    CaseRead,
    CaseStatistics,
    CaseSummary,
    CaseUpdate,
)
from Backend.App.Schemas.Events import EventRead
from Database.PostgreSQL.Models import Case, Evidence
from Database.PostgreSQL.Models.Case import CASE_PRIORITIES, CASE_STATUSES
from Database.PostgreSQL.Models.Evidence import MEDIA_TYPES
from Database.PostgreSQL.Repositories import CaseRepository, EventRepository, EvidenceRepository
from Database.PostgreSQL.Repositories.CaseRepository import CaseFilters


def _publish(session: Session, case: Case, event_type: str, payload: dict) -> None:
    Outbox.publish(session, event_type, aggregate_type="case", aggregate_id=case.id, case_id=case.id,
                   payload={"case_number": case.display_number, "title": case.title, "status": case.status} | payload)


def get_case(session: Session, case_id: uuid.UUID, *, for_update: bool = False) -> Case:
    case = CaseRepository.get(session, case_id, for_update=for_update)
    if case is None:
        raise NextronError(404, ErrorCode.CASE_NOT_FOUND, "The requested case does not exist")
    return case


def read_case(session: Session, case: Case) -> CaseRead:
    last = CaseRepository.last_activity(session, case.id) or case.updated_at
    return CaseRead.of(case, CaseRepository.evidence_count(session, case.id), last)


def create_case(session: Session, data: CaseCreate, actor: str) -> CaseRead:
    case = Case(
        title=data.title,
        description=data.description,
        objectives=data.objectives,
        category=data.category,
        priority=data.priority,
        tags=data.tags,
        notes=data.notes,
        status="OPEN",
        created_by=actor,
        revision=1,
    )
    session.add(case)
    session.flush()
    EventRepository.append(
        session,
        case_id=case.id,
        event_type="case.created",
        actor=actor,
        payload={"title": case.title, "priority": case.priority, "category": case.category, "status": case.status},
    )
    _publish(session, case, "case.created", {"priority": case.priority})
    session.commit()
    session.refresh(case)
    return read_case(session, case)


def list_cases(session: Session, filters: CaseFilters, *, page: int, page_size: int) -> tuple[list[CaseRead], int]:
    rows, total = CaseRepository.list_page(session, filters, page=page, page_size=page_size)
    return [CaseRead.of(case, count, last or case.updated_at) for case, count, last in rows], total


def update_case(session: Session, case_id: uuid.UUID, patch: CaseUpdate, actor: str) -> CaseRead:
    case = get_case(session, case_id, for_update=True)
    Lifecycle.ensure_writable(case)

    changes = {}
    for field, new_value in patch.model_dump(exclude_unset=True).items():
        old_value = getattr(case, field)
        if field == "tags":
            old_value = list(old_value or [])
        if old_value != new_value:
            changes[field] = {"from": old_value, "to": new_value}
            setattr(case, field, new_value)

    if not changes:
        session.rollback()
        return read_case(session, case)

    case.revision += 1
    case.updated_at = func.now()
    EventRepository.append(
        session, case_id=case.id, event_type="case.updated", actor=actor, payload={"revision": case.revision, "changes": changes}
    )
    _publish(session, case, "case.updated", {"revision": case.revision, "fields": sorted(changes)})
    session.commit()
    session.refresh(case)
    return read_case(session, case)


def archive_case(session: Session, case_id: uuid.UUID, request: ArchiveRequest, actor: str) -> CaseRead:
    case = get_case(session, case_id, for_update=True)
    previous = Lifecycle.archive(case)
    case.archived_at = func.now()
    case.revision += 1
    case.updated_at = func.now()
    EventRepository.append(
        session,
        case_id=case.id,
        event_type="case.archived",
        actor=actor,
        payload={"from_status": previous, "reason": request.reason, "revision": case.revision},
    )
    _publish(session, case, "case.archived", {"revision": case.revision})
    session.commit()
    session.refresh(case)
    return read_case(session, case)


def reopen_case(session: Session, case_id: uuid.UUID, actor: str) -> CaseRead:
    case = get_case(session, case_id, for_update=True)
    restored = Lifecycle.reopen(case)
    case.archived_at = None
    case.revision += 1
    case.updated_at = func.now()
    EventRepository.append(
        session,
        case_id=case.id,
        event_type="case.reopened",
        actor=actor,
        payload={"to_status": restored, "revision": case.revision},
    )
    _publish(session, case, "case.reopened", {"revision": case.revision})
    session.commit()
    session.refresh(case)
    return read_case(session, case)


def overall_statistics(session: Session) -> CaseStatistics:
    by_status = {status: 0 for status in CASE_STATUSES} | CaseRepository.counts_by(session, Case.status)
    by_priority = {priority: 0 for priority in CASE_PRIORITIES} | CaseRepository.counts_by(session, Case.priority)
    total = sum(by_status.values())
    return CaseStatistics(
        total_cases=total,
        active_cases=total - by_status["ARCHIVED"] - by_status["CLOSED"],
        by_status=by_status,
        by_priority=by_priority,
        total_evidence=sum(EvidenceRepository.counts_by(session, Evidence.media_type).values()),
    )


def case_statistics(session: Session, case_id: uuid.UUID) -> CaseEvidenceStatistics:
    get_case(session, case_id)
    by_media = {media: 0 for media in MEDIA_TYPES} | EvidenceRepository.counts_by(session, Evidence.media_type, case_id=case_id)
    return CaseEvidenceStatistics(
        case_id=case_id,
        evidence_total=sum(by_media.values()),
        evidence_by_media_type=by_media,
        evidence_total_bytes=EvidenceRepository.total_bytes(session, case_id=case_id),
        event_count=EventRepository.count_for_case(session, case_id),
    )


def case_summary(session: Session, case_id: uuid.UUID, *, recent: int = 10) -> CaseSummary:
    case = get_case(session, case_id)
    events = EventRepository.latest(session, case_id=case_id, limit=recent)
    return CaseSummary(
        case=read_case(session, case),
        statistics=case_statistics(session, case_id),
        recent_events=[EventRead.of(e) for e in events],
        last_activity_at=events[0].occurred_at if events else case.updated_at,
    )
