"""NEX-MET response schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from Database.PostgreSQL.Models import EvidenceMetadata


class MetadataRead(BaseModel):
    metadata_id: uuid.UUID
    evidence_id: uuid.UUID
    status: Literal["EXTRACTED", "UNAVAILABLE", "FAILED"]
    extractor: str
    extractor_version: str
    input_sha256: str = Field(description="Recorded SHA-256 of the evidence the extractor read")
    extracted_at: datetime
    version_count: int = Field(description="How many extractions exist for this evidence; this is the latest")
    summary: dict[str, Any]
    raw: dict[str, Any] | None = Field(description="Full FFprobe output for video/audio; null for images")
    error: str | None

    @classmethod
    def of(cls, row: EvidenceMetadata, version_count: int) -> "MetadataRead":
        return cls(
            metadata_id=row.id,
            evidence_id=row.evidence_id,
            status=row.status,
            extractor=row.extractor,
            extractor_version=row.extractor_version,
            input_sha256=row.input_sha256,
            extracted_at=row.extracted_at,
            version_count=version_count,
            summary=row.summary,
            raw=row.raw,
            error=row.error,
        )
