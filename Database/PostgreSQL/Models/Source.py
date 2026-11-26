"""NEX-SRC source records and their retrieval history (archive §4, module 09).

A source record is a URL an investigator added to a case. Each retrieval attempt appends a `source_observations`
row (append-only), whatever its outcome; the record keeps only the latest state and its revision, so downstream
modules (NEX-FPM, NEX-MOC) pin the exact revision they used. A publication time is always the one the source
*claims*; NEXTRON's own retrieval time is recorded separately and is never presented as the original's time.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base

SOURCE_STATES = ("PENDING", "RETRIEVED", "METADATA_ONLY", "UNAVAILABLE", "RESTRICTED", "NOT_FOUND", "UNSUPPORTED",
                 "RATE_LIMITED", "BLOCKED", "FAILED")
PLATFORMS = ("GENERIC", "YOUTUBE", "X", "INSTAGRAM", "FACEBOOK", "TIKTOK", "WHATSAPP")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class SourceRecord(Base):
    __tablename__ = "source_records"
    __table_args__ = (
        CheckConstraint(_in("state", SOURCE_STATES), name="state_valid"),
        CheckConstraint(_in("platform", PLATFORMS), name="platform_valid"),
        CheckConstraint("revision >= 1", name="revision_positive"),
        UniqueConstraint("case_id", "normalized_url", name="uq_source_records_case_url"),
        Index("ix_source_records_case_id_created_at", "case_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_number: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"))
    url: Mapped[str] = mapped_column(Text)                    # as the investigator entered it
    normalized_url: Mapped[str] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16), default="PENDING")
    state_detail: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1)  # +1 for every finished retrieval
    title: Mapped[str | None] = mapped_column(Text)
    claimed_publication_time: Mapped[str | None] = mapped_column(String(64))  # as stated by the source, unparsed
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="RESTRICT"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def display_number(self) -> str:
        return f"SRC-{self.source_number:04d}"


class SourceObservation(Base):
    """One retrieval attempt: what was asked, what came back, and what NEXTRON did with it."""

    __tablename__ = "source_observations"
    __table_args__ = (
        CheckConstraint(_in("outcome", SOURCE_STATES), name="outcome_valid"),
        UniqueConstraint("source_id", "revision", name="uq_source_observations_source_revision"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("source_records.id", ondelete="RESTRICT"))
    revision: Mapped[int] = mapped_column(Integer)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="RESTRICT"))
    connector: Mapped[str] = mapped_column(String(32))
    outcome: Mapped[str] = mapped_column(String(16))
    detail: Mapped[str | None] = mapped_column(Text)
    requested_url: Mapped[str] = mapped_column(Text)
    final_url: Mapped[str | None] = mapped_column(Text)
    redirects: Mapped[list] = mapped_column(JSONB, default=list)       # each hop: url, status, resolved address
    http_status: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(255))
    bytes_received: Mapped[int | None] = mapped_column(BigInteger)
    media_sha256: Mapped[str | None] = mapped_column(String(64))
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="RESTRICT"))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)  # title, claimed times, og/twitter tags
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
