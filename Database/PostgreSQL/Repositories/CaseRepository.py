"""Case queries. Filtering, sorting and paging happen in SQL, never in Python."""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from Database.PostgreSQL.Models import Case, Evidence, InvestigationEvent
from Database.PostgreSQL.Models.Case import CASE_STATUSES as _ALL_STATUSES

_CASE_NUMBER = re.compile(r"(?i)(?:CASE-)?0*(\d{1,18})")


def _last_activity():
    """Most recent event time for the case; every case has at least its case.created event."""
    return (
        select(func.max(InvestigationEvent.occurred_at))
        .where(InvestigationEvent.case_id == Case.id)
        .correlate(Case)
        .scalar_subquery()
    )


SORTABLE = {
    "created_at": Case.created_at,
    "updated_at": Case.updated_at,
    "last_activity_at": _last_activity(),
    "title": Case.title,
    "priority": Case.priority,
    "case_number": Case.case_number,
    "status": Case.status,
}


@dataclass(frozen=True)
class CaseFilters:
    search: str | None = None
    statuses: tuple[str, ...] = ()
    priorities: tuple[str, ...] = ()
    created_from: datetime | None = None
    created_to: datetime | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    hide_test_records: bool = False


# Titles the automated suites, benchmarks and drills give the records they create (Tests/, Benchmarks/, Scripts/Testing).
# Hiding them is an explicit, reversible list filter; the records themselves are never changed.
TEST_RECORD_PREFIXES = ("[E2E]", "[Bench]", "[Drill]", "[Test]", "[Smoke]")


def is_test_record(title: str) -> bool:
    return title.startswith(TEST_RECORD_PREFIXES)


def get(session: Session, case_id: uuid.UUID, *, for_update: bool = False) -> Case | None:
    query = select(Case).where(Case.id == case_id)
    if for_update:
        query = query.with_for_update()
    return session.scalars(query).first()


def _evidence_count():
    return (
        select(func.count(Evidence.id)).where(Evidence.case_id == Case.id).correlate(Case).scalar_subquery()
    )


def _filtered(filters: CaseFilters) -> Select:
    query = select(Case)
    if filters.statuses:
        query = query.where(Case.status.in_(filters.statuses))
    else:
        query = query.where(Case.status != "ARCHIVED")  # archived cases are listed only on request
    if filters.priorities:
        query = query.where(Case.priority.in_(filters.priorities))
    if filters.created_from:
        query = query.where(Case.created_at >= filters.created_from)
    if filters.created_to:
        query = query.where(Case.created_at < filters.created_to)
    if filters.hide_test_records:
        for prefix in TEST_RECORD_PREFIXES:
            query = query.where(~Case.title.startswith(prefix, autoescape=True))
    if filters.search:
        escaped = filters.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions = [Case.title.ilike(pattern, escape="\\"), Case.description.ilike(pattern, escape="\\")]
        number = _CASE_NUMBER.fullmatch(filters.search.strip())
        if number:
            conditions.append(Case.case_number == int(number.group(1)))
        query = query.where(or_(*conditions))
    return query


def list_page(
    session: Session, filters: CaseFilters, *, page: int, page_size: int
) -> tuple[list[tuple[Case, int, datetime]], int]:
    """Rows are (case, evidence_count, last_activity_at)."""
    base = _filtered(filters)
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    column = SORTABLE[filters.sort_by]
    order = column.asc() if filters.sort_order == "asc" else column.desc()
    query = (
        base.add_columns(_evidence_count().label("evidence_count"), _last_activity().label("last_activity_at"))
        .order_by(order, Case.case_number.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [(row[0], row[1], row[2]) for row in session.execute(query)], total


def evidence_count(session: Session, case_id: uuid.UUID) -> int:
    return session.scalar(select(func.count(Evidence.id)).where(Evidence.case_id == case_id)) or 0


def last_activity(session: Session, case_id: uuid.UUID) -> datetime | None:
    return session.scalar(select(func.max(InvestigationEvent.occurred_at)).where(InvestigationEvent.case_id == case_id))


def search(session: Session, text: str, *, limit: int) -> list[Case]:
    """Title, description or case number; archived cases included (search should find everything)."""
    filters = CaseFilters(search=text, statuses=tuple(s for s in _ALL_STATUSES))
    return list(session.scalars(_filtered(filters).order_by(Case.updated_at.desc()).limit(limit)))


def counts_by(session: Session, column) -> dict[str, int]:
    return {key: count for key, count in session.execute(select(column, func.count()).group_by(column))}
