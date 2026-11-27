"""NEX-EVD preserved evidence: exact received bytes, their SHA-256 and storage location.

A row exists only after the bytes are in protected storage and re-verified, so every row
is PRESERVED. The hash, size, storage key and case can never change (database trigger).
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base

MEDIA_TYPES = ("IMAGE", "VIDEO", "AUDIO")
PRESERVATION_STATUSES = ("PRESERVED",)
SOURCE_TYPES = ("USER_UPLOAD", "SHARED_FILE", "SCREENSHOT", "SCREEN_RECORDING", "SOURCE_RETRIEVAL")
ACQUISITION_METHODS = ("DIRECT_UPLOAD", "SHARE_INTENT", "SCREEN_CAPTURE", "CONNECTOR_RETRIEVAL")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(_in("media_type", MEDIA_TYPES), name="media_type_valid"),
        CheckConstraint(_in("preservation_status", PRESERVATION_STATUSES), name="preservation_status_valid"),
        CheckConstraint(_in("source_type", SOURCE_TYPES), name="source_type_valid"),
        CheckConstraint(_in("acquisition_method", ACQUISITION_METHODS), name="acquisition_method_valid"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        Index("ix_evidence_case_id_received_at", "case_id", "received_at"),
        Index("ix_evidence_case_media_number", "case_id", "media_type", "evidence_number"),
        Index("ix_evidence_sha256", "sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_number: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"))
    original_filename: Mapped[str] = mapped_column(String(255))
    declared_content_type: Mapped[str | None] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(16))
    detected_format: Mapped[str] = mapped_column(String(32))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    preservation_status: Mapped[str] = mapped_column(String(16), default="PRESERVED")
    source_type: Mapped[str] = mapped_column(String(32))
    acquisition_method: Mapped[str] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)
    acquired_by: Mapped[str] = mapped_column(String(100))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    preserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def display_number(self) -> str:
        return f"EVD-{self.evidence_number:04d}"
