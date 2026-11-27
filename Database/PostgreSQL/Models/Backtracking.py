"""Versioned, case-scoped local video comparison history."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base


class BacktrackingComparison(Base):
    __tablename__ = "backtracking_comparisons"
    __table_args__ = (
        CheckConstraint("seed_evidence_id <> candidate_evidence_id", name="distinct_evidence"),
        UniqueConstraint("case_id", "seed_evidence_id", "candidate_evidence_id", "seed_sha256",
                         "candidate_sha256", "algorithm", "fingerprint_algorithm", name="uq_btk_comparison_inputs"),
        Index("ix_btk_comparisons_case_created", "case_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"))
    seed_evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="RESTRICT"))
    candidate_evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="RESTRICT"))
    seed_sha256: Mapped[str] = mapped_column(String(64))
    candidate_sha256: Mapped[str] = mapped_column(String(64))
    algorithm: Mapped[str] = mapped_column(String(64))
    fingerprint_algorithm: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    result: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
