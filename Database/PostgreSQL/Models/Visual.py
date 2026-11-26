"""Authoritative, versioned image embeddings; Qdrant is a rebuildable ANN projection."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base


class VisualEmbedding(Base):
    __tablename__ = "visual_embeddings"
    __table_args__ = (
        UniqueConstraint("evidence_id", "model_key", name="uq_visual_embeddings_evidence_model"),
        Index("ix_visual_embeddings_case_model", "case_id", "model_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="RESTRICT"))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"))
    model_key: Mapped[str] = mapped_column(String(160))
    vector: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
