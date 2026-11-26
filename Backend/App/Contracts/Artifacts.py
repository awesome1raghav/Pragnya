"""Derived artifacts and the references modules use to name their inputs.

Modules never pass data to each other directly (plan decision D-4). An execution's inputs are
references to persisted records, each pinned to an exact version or digest, so a result can always be
traced to precisely what it read and the run can be reproduced.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from Database.PostgreSQL.Models.ArtifactRecord import ARTIFACT_KINDS


class ArtifactKind(StrEnum):
    FRAME = "FRAME"
    FRAME_SET = "FRAME_SET"
    AUDIO_TRACK = "AUDIO_TRACK"
    THUMBNAIL = "THUMBNAIL"
    HEATMAP = "HEATMAP"
    FEATURE_VECTOR = "FEATURE_VECTOR"
    FINGERPRINT = "FINGERPRINT"
    REPORT_PDF = "REPORT_PDF"
    REPORT_JSON = "REPORT_JSON"
    OTHER = "OTHER"


assert {k.value for k in ArtifactKind} == set(ARTIFACT_KINDS)


class ArtifactRef(BaseModel):
    """A stored derived artifact as a module result lists it. The storage key stays server-side."""

    model_config = ConfigDict(extra="forbid")
    artifact_id: uuid.UUID
    kind: ArtifactKind
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    mime_type: str = Field(min_length=1, max_length=100)
    evidence_id: uuid.UUID | None = Field(default=None, description="The original it was derived from")
    derived_from_artifact_id: uuid.UUID | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class InputKind(StrEnum):
    EVIDENCE = "EVIDENCE"            # a preserved original, pinned by its SHA-256
    MODULE_RESULT = "MODULE_RESULT"  # another module's result, pinned by result ID
    ARTIFACT = "ARTIFACT"            # a derived artifact, pinned by its SHA-256
    SOURCE_RECORD = "SOURCE_RECORD"  # a NEX-SRC source record, pinned by its revision


class InputReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: InputKind
    id: uuid.UUID
    module_id: str | None = Field(default=None, pattern=r"^NEX-[A-Z]{2,3}$", description="For MODULE_RESULT: which module produced it")
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    revision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _pinned(self):
        if self.kind in (InputKind.EVIDENCE, InputKind.ARTIFACT) and not self.sha256:
            raise ValueError(f"{self.kind} inputs are pinned by sha256")
        if self.kind is InputKind.MODULE_RESULT and not self.module_id:
            raise ValueError("MODULE_RESULT inputs name the module that produced them")
        if self.kind is InputKind.SOURCE_RECORD and self.revision is None:
            raise ValueError("SOURCE_RECORD inputs are pinned by revision")
        return self
