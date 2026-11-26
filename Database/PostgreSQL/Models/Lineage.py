"""NEX-FPM fingerprints and NEX-MOC version relationships (archive §4, modules 10 and 11).

`media_fingerprints` holds the canonical fingerprints FPM computed for an evidence item (append-only; a new
algorithm version adds rows, it does not overwrite). `media_relationships` holds the candidate relationships MOC
proposed between two evidence items in a case. Every relationship is a CANDIDATE: similarity is never presented as
proof of common origin, and NEX-INV (Step 7) is where an investigator confirms or rejects one.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base

FINGERPRINT_KINDS = ("IMAGE_DHASH", "IMAGE_PHASH", "VIDEO_FRAME_DHASH", "AUDIO_SUBFINGERPRINT")
RELATIONSHIP_KINDS = ("NEAR_DUPLICATE", "SAME_CONTENT_VARIANT", "FRAME_OF_VIDEO", "SHARED_VIDEO_SEGMENT", "SHARED_AUDIO")
RELATIONSHIP_STATUSES = ("CANDIDATE",)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class MediaFingerprint(Base):
    __tablename__ = "media_fingerprints"
    __table_args__ = (
        CheckConstraint(_in("kind", FINGERPRINT_KINDS), name="kind_valid"),
        UniqueConstraint("evidence_id", "kind", "algorithm", name="uq_media_fingerprints_evidence_kind_algorithm"),
        Index("ix_media_fingerprints_case_id_kind", "case_id", "kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="RESTRICT"))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(32))
    algorithm: Mapped[str] = mapped_column(String(64))            # e.g. nextron-fpm/1:dhash64
    value: Mapped[dict] = mapped_column(JSONB)                    # {"hash": hex} or {"frames": [{t, hash}]} or {"rate", "hop", "bits": [...]}
    execution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_executions.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MediaRelationship(Base):
    __tablename__ = "media_relationships"
    __table_args__ = (
        CheckConstraint(_in("kind", RELATIONSHIP_KINDS), name="kind_valid"),
        CheckConstraint(_in("status", RELATIONSHIP_STATUSES), name="status_valid"),
        CheckConstraint("evidence_a <> evidence_b", name="distinct_evidence"),
        Index("ix_media_relationships_case_id", "case_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"))
    evidence_a: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="RESTRICT"))
    evidence_b: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="CANDIDATE")
    similarity: Mapped[float] = mapped_column(Float)              # 0..1, from the fingerprint distance (method stated in basis)
    earlier_observed: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # which one was observed earlier, if known
    ordering_basis: Mapped[str | None] = mapped_column(Text)      # why (claimed source publication times), or null
    basis: Mapped[dict] = mapped_column(JSONB)                    # distances, offsets, fingerprint IDs used
    execution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_executions.id", ondelete="RESTRICT"))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
