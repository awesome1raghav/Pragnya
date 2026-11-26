"""NEX-CM investigation case."""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, BigInteger, CheckConstraint, DateTime, Identity, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base

# Canonical case lifecycle (archive §10.2). DRAFT is omitted: a case exists only once committed.
CASE_STATUSES = (
    "OPEN",
    "EVIDENCE_COLLECTION",
    "INVESTIGATION_IN_PROGRESS",
    "REVIEW_REQUIRED",
    "REVIEW_COMPLETED",
    "REPORT_AVAILABLE",
    "CLOSED",
    "ARCHIVED",
)
CASE_PRIORITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
# Investigation category (Flowchart B §7.4). Reversible default vocabulary; OTHER when unsure.
CASE_CATEGORIES = ("MEDIA_MANIPULATION", "SYNTHETIC_MEDIA", "SOURCE_VERIFICATION", "CONTEXT_VERIFICATION", "OTHER")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint(_in("status", CASE_STATUSES), name="status_valid"),
        CheckConstraint(_in("priority", CASE_PRIORITIES), name="priority_valid"),
        CheckConstraint(_in("category", CASE_CATEGORIES), name="category_valid"),
        CheckConstraint(
            "archived_from_status IS NULL OR " + _in("archived_from_status", CASE_STATUSES[:-1]),
            name="archived_from_status_valid",
        ),
        CheckConstraint("(status = 'ARCHIVED') = (archived_at IS NOT NULL)", name="archived_at_matches_status"),
        CheckConstraint("char_length(btrim(title)) > 0", name="title_not_blank"),
        Index("ix_cases_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_number: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    objectives: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), default="OTHER", server_default=text("'OTHER'"))
    status: Mapped[str] = mapped_column(String(32), default="OPEN")
    archived_from_status: Mapped[str | None] = mapped_column(String(32))
    priority: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list, server_default=text("'{}'"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(100))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def display_number(self) -> str:
        return f"CASE-{self.case_number:04d}"
