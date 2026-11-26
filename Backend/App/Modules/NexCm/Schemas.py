"""NEX-CM request and response schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from Backend.App.Schemas.Events import EventRead
from Database.PostgreSQL.Models import Case
from Database.PostgreSQL.Models.Case import CASE_CATEGORIES, CASE_STATUSES

CaseStatus = Literal[
    "OPEN",
    "EVIDENCE_COLLECTION",
    "INVESTIGATION_IN_PROGRESS",
    "REVIEW_REQUIRED",
    "REVIEW_COMPLETED",
    "REPORT_AVAILABLE",
    "CLOSED",
    "ARCHIVED",
]
CasePriority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
CaseCategory = Literal["MEDIA_MANIPULATION", "SYNTHETIC_MEDIA", "SOURCE_VERIFICATION", "CONTEXT_VERIFICATION", "OTHER"]
assert set(CaseStatus.__args__) == set(CASE_STATUSES)  # one vocabulary, model and API
assert set(CaseCategory.__args__) == set(CASE_CATEGORIES)


def _clean_tags(tags: list[str]) -> list[str]:
    seen: list[str] = []
    for tag in tags:
        tag = tag.strip()
        if not tag:
            raise ValueError("Tags cannot be blank")
        if len(tag) > 50:
            raise ValueError("Tags are at most 50 characters")
        if tag not in seen:
            seen.append(tag)
    return seen


class CaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    objectives: str | None = Field(default=None, max_length=5_000, description="What the investigation must establish")
    category: CaseCategory = "OTHER"
    priority: CasePriority = "MEDIUM"
    tags: list[str] = Field(default_factory=list, max_length=20)
    notes: str | None = Field(default=None, max_length=20_000)

    @field_validator("tags")
    @classmethod
    def _tags(cls, value: list[str]) -> list[str]:
        return _clean_tags(value)


class CaseUpdate(BaseModel):
    """Only these fields can be patched. Status changes only through lifecycle actions."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    objectives: str | None = Field(default=None, max_length=5_000)
    category: CaseCategory | None = None
    priority: CasePriority | None = None
    tags: list[str] | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=20_000)

    @field_validator("title", "priority", "category", "tags", mode="before")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")
        return value

    @field_validator("tags")
    @classmethod
    def _tags(cls, value):
        return _clean_tags(value) if value is not None else value


class ArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str | None = Field(default=None, max_length=500)


class CaseRead(BaseModel):
    case_id: uuid.UUID
    case_number: str = Field(examples=["CASE-0001"])
    title: str
    description: str | None
    objectives: str | None
    category: CaseCategory
    status: CaseStatus
    priority: CasePriority
    tags: list[str]
    notes: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    revision: int
    evidence_count: int
    last_activity_at: datetime = Field(description="Time of the most recent recorded event in this case")

    @classmethod
    def of(cls, case: Case, evidence_count: int, last_activity_at: datetime) -> "CaseRead":
        return cls(
            case_id=case.id,
            case_number=case.display_number,
            title=case.title,
            description=case.description,
            objectives=case.objectives,
            category=case.category,
            status=case.status,
            priority=case.priority,
            tags=list(case.tags or []),
            notes=case.notes,
            created_by=case.created_by,
            created_at=case.created_at,
            updated_at=case.updated_at,
            archived_at=case.archived_at,
            revision=case.revision,
            evidence_count=evidence_count,
            last_activity_at=last_activity_at,
        )


class CaseStatistics(BaseModel):
    """Counts over all cases. Every status and priority is listed, including real zeros."""

    total_cases: int
    active_cases: int = Field(description="All cases that are not ARCHIVED or CLOSED")
    by_status: dict[str, int]
    by_priority: dict[str, int]
    total_evidence: int


class CaseEvidenceStatistics(BaseModel):
    case_id: uuid.UUID
    evidence_total: int
    evidence_by_media_type: dict[str, int]
    evidence_total_bytes: int
    event_count: int


class CaseSummary(BaseModel):
    case: CaseRead
    statistics: CaseEvidenceStatistics
    recent_events: list[EventRead]
    last_activity_at: datetime
