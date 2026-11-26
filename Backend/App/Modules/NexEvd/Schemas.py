"""NEX-EVD response schemas. Storage keys are never exposed."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from Database.PostgreSQL.Models import Evidence

SourceType = Literal["USER_UPLOAD", "SHARED_FILE", "SCREENSHOT", "SCREEN_RECORDING", "SOURCE_RETRIEVAL"]
AcquisitionMethod = Literal["DIRECT_UPLOAD", "SHARE_INTENT", "SCREEN_CAPTURE", "CONNECTOR_RETRIEVAL"]


class EvidenceRead(BaseModel):
    evidence_id: uuid.UUID
    evidence_number: str = Field(examples=["EVD-0001"])
    case_id: uuid.UUID
    filename: str = Field(description="Client-supplied name, recorded as a label only")
    declared_content_type: str | None = Field(description="Client-supplied Content-Type; not trusted")
    media_type: Literal["IMAGE", "VIDEO", "AUDIO"]
    detected_format: str
    mime_type: str = Field(description="Determined by NEXTRON from the bytes")
    file_size: int
    sha256: str
    hash_algorithm: Literal["SHA-256"] = "SHA-256"
    preservation_status: Literal["PRESERVED"]
    source_type: SourceType
    acquisition_method: AcquisitionMethod
    description: str | None
    acquired_by: str
    received_at: datetime
    preserved_at: datetime
    created_at: datetime = Field(description="Same as preserved_at: when the record was committed")

    @classmethod
    def of(cls, evidence: Evidence) -> "EvidenceRead":
        return cls(
            evidence_id=evidence.id,
            evidence_number=evidence.display_number,
            case_id=evidence.case_id,
            filename=evidence.original_filename,
            declared_content_type=evidence.declared_content_type,
            media_type=evidence.media_type,
            detected_format=evidence.detected_format,
            mime_type=evidence.mime_type,
            file_size=evidence.size_bytes,
            sha256=evidence.sha256,
            preservation_status=evidence.preservation_status,
            source_type=evidence.source_type,
            acquisition_method=evidence.acquisition_method,
            description=evidence.description,
            acquired_by=evidence.acquired_by,
            received_at=evidence.received_at,
            preserved_at=evidence.preserved_at,
            created_at=evidence.preserved_at,
        )


class EvidenceListItem(EvidenceRead):
    """Evidence in a cross-case listing, with its investigation named."""

    case_number: str
    case_title: str

    @classmethod
    def of_row(cls, evidence: Evidence, case_number: int, case_title: str) -> "EvidenceListItem":
        return cls(**EvidenceRead.of(evidence).model_dump(), case_number=f"CASE-{case_number:04d}", case_title=case_title)


class DuplicateReference(BaseModel):
    evidence_id: uuid.UUID
    evidence_number: str


class JobReference(BaseModel):
    job_id: uuid.UUID
    job_number: str = Field(examples=["JOB-0001"])
    state: str


class UploadedEvidence(EvidenceRead):
    duplicates_in_case: list[DuplicateReference] = Field(
        description="Earlier evidence in this case with identical bytes. Each upload keeps its own record and custody."
    )
    analysis_job: JobReference | None = Field(
        description="The T-MIR investigation run queued with this evidence (null when AUTO_ANALYZE_ON_UPLOAD is off). "
                    "Metadata and analysis results appear when a worker has run it."
    )


class IntegrityVerification(BaseModel):
    evidence_id: uuid.UUID
    result: Literal["MATCH", "MISMATCH", "MISSING"]
    recorded_sha256: str
    computed_sha256: str | None
    recorded_size: int
    computed_size: int | None
    verified_at: datetime
    note: str = "A match shows the stored bytes equal the bytes recorded at preservation. It does not show the content is authentic."


class IntegrityState(BaseModel):
    evidence_id: uuid.UUID
    recorded_sha256: str
    hash_algorithm: Literal["SHA-256"] = "SHA-256"
    recorded_size: int
    preserved_at: datetime
    last_verification: IntegrityVerification | None = Field(description="Most recent verification, or null if never verified")


class EvidenceStatistics(BaseModel):
    total_evidence: int
    by_media_type: dict[str, int]
    by_preservation_status: dict[str, int]
    total_bytes: int
