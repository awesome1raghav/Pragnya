"""Evidence and evidence-metadata queries."""

import re
import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from Database.PostgreSQL.Models import Case, Evidence, EvidenceMetadata

_EVIDENCE_NUMBER = re.compile(r"(?i)(?:EVD-)?0*(\d{1,18})")
_HASH_PREFIX = re.compile(r"(?i)[0-9a-f]{6,64}")


def _text_condition(text: str):
    """Filename substring, evidence number (EVD-0001 or 1), or SHA-256 prefix (6+ hex characters)."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    conditions = [Evidence.original_filename.ilike(f"%{escaped}%", escape="\\")]
    stripped = text.strip()
    if number := _EVIDENCE_NUMBER.fullmatch(stripped):
        conditions.append(Evidence.evidence_number == int(number.group(1)))
    if _HASH_PREFIX.fullmatch(stripped):
        conditions.append(Evidence.sha256.startswith(stripped.lower()))
    return or_(*conditions)


def _with_case(query: Select) -> Select:
    return query.join(Case, Case.id == Evidence.case_id).add_columns(Case.case_number, Case.title)


def list_all(
    session: Session,
    *,
    page: int,
    page_size: int,
    case_id: uuid.UUID | None = None,
    media_type: str | None = None,
    text: str | None = None,
) -> tuple[list[tuple[Evidence, int, str]], int]:
    """Evidence across cases with each row's case number and title: (evidence, case_number, case_title)."""
    query = select(Evidence)
    if case_id is not None:
        query = query.where(Evidence.case_id == case_id)
    if media_type:
        query = query.where(Evidence.media_type == media_type)
    if text:
        query = query.where(_text_condition(text))
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.execute(
        _with_case(query)
        .order_by(Evidence.received_at.desc(), Evidence.evidence_number.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [(row[0], row[1], row[2]) for row in rows], total


def search(session: Session, text: str, *, limit: int) -> list[tuple[Evidence, int, str]]:
    query = _with_case(select(Evidence).where(_text_condition(text))).order_by(Evidence.received_at.desc()).limit(limit)
    return [(row[0], row[1], row[2]) for row in session.execute(query)]


def get(session: Session, evidence_id: uuid.UUID) -> Evidence | None:
    return session.get(Evidence, evidence_id)


def list_for_case(session: Session, case_id: uuid.UUID, *, page: int, page_size: int, media_type: str | None = None):
    query = select(Evidence).where(Evidence.case_id == case_id)
    if media_type:
        query = query.where(Evidence.media_type == media_type)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(Evidence.received_at.desc(), Evidence.evidence_number.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total


def same_hash_in_case(session: Session, case_id: uuid.UUID, sha256: str, exclude_id: uuid.UUID | None = None) -> list[Evidence]:
    query = select(Evidence).where(Evidence.case_id == case_id, Evidence.sha256 == sha256)
    if exclude_id is not None:
        query = query.where(Evidence.id != exclude_id)
    return list(session.scalars(query.order_by(Evidence.evidence_number)))


def latest_metadata(session: Session, evidence_id: uuid.UUID) -> EvidenceMetadata | None:
    query = (
        select(EvidenceMetadata)
        .where(EvidenceMetadata.evidence_id == evidence_id)
        .order_by(EvidenceMetadata.extracted_at.desc())
        .limit(1)
    )
    return session.scalars(query).first()


def metadata_versions(session: Session, evidence_id: uuid.UUID) -> int:
    return session.scalar(select(func.count()).where(EvidenceMetadata.evidence_id == evidence_id)) or 0


def counts_by(session: Session, column, *, case_id: uuid.UUID | None = None) -> dict[str, int]:
    query = select(column, func.count()).group_by(column)
    if case_id is not None:
        query = query.where(Evidence.case_id == case_id)
    return {key: count for key, count in session.execute(query)}


def total_bytes(session: Session, *, case_id: uuid.UUID | None = None) -> int:
    query = select(func.coalesce(func.sum(Evidence.size_bytes), 0))
    if case_id is not None:
        query = query.where(Evidence.case_id == case_id)
    return int(session.scalar(query) or 0)


def all_storage_keys(session: Session) -> dict[str, uuid.UUID]:
    return {key: evidence_id for key, evidence_id in session.execute(select(Evidence.storage_key, Evidence.id))}
