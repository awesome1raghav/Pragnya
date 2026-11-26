"""NEX-MET extracted technical metadata. Versioned: each extraction is a new row."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base

METADATA_STATUSES = ("EXTRACTED", "UNAVAILABLE", "FAILED")


class EvidenceMetadata(Base):
    __tablename__ = "evidence_metadata"
    __table_args__ = (
        CheckConstraint("status IN ('EXTRACTED', 'UNAVAILABLE', 'FAILED')", name="status_valid"),
        CheckConstraint("input_sha256 ~ '^[0-9a-f]{64}$'", name="input_sha256_hex"),
        Index("ix_evidence_metadata_evidence_id_extracted_at", "evidence_id", "extracted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16))
    extractor: Mapped[str] = mapped_column(String(50))
    extractor_version: Mapped[str] = mapped_column(String(200))
    input_sha256: Mapped[str] = mapped_column(String(64))
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    raw: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
