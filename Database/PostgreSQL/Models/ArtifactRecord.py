"""Derived artifacts (frames, audio tracks, heatmaps, feature vectors, report files) and their hashes.

Every derived item is stored separately from the original with its own SHA-256 and a reference to what it
was derived from (archive §12.2 step 3). Records are immutable: a trigger rejects UPDATE and DELETE.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base

ARTIFACT_KINDS = (
    "FRAME", "FRAME_SET", "AUDIO_TRACK", "THUMBNAIL", "HEATMAP", "FEATURE_VECTOR", "FINGERPRINT",
    "REPORT_PDF", "REPORT_JSON", "OTHER",
)


class ArtifactRecord(Base):
    __tablename__ = "artifact_records"
    __table_args__ = (
        CheckConstraint(f"kind IN ({', '.join(repr(k) for k in ARTIFACT_KINDS)})", name="kind_valid"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        CheckConstraint("size_bytes >= 0", name="size_non_negative"),
        CheckConstraint("evidence_id IS NOT NULL OR derived_from_artifact_id IS NOT NULL OR kind IN ('REPORT_PDF', 'REPORT_JSON')", name="has_parent"),
        Index("ix_artifact_records_evidence_id", "evidence_id"),
        Index("ix_artifact_records_execution_id", "execution_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"))
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="RESTRICT"))
    derived_from_artifact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_records.id", ondelete="RESTRICT"))
    execution_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_executions.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(32))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    mime_type: Mapped[str] = mapped_column(String(100))
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)  # e.g. frame timestamp, sample rate, model version
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
