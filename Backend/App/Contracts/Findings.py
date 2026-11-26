"""The structured finding every module returns (Flowchart B §4.2, §5.2; archive §5.2).

Rules enforced by validation:
- `assertion` separates measured observations from inferences and from inconclusive outcomes.
- `score` is the method's raw number and must say what kind of number it is (`score_kind`).
- `confidence` is allowed only for a calibrated probability, with the calibration basis stated.
  When no calibration exists, confidence is null. Nothing invents a confidence value.
- A finding names the evidence it is about and may point to the artifacts that support it.
"""

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from Database.PostgreSQL.Models.AnalysisFinding import ASSERTIONS, SCORE_KINDS


class Assertion(StrEnum):
    OBSERVATION = "OBSERVATION"    # measured directly, e.g. "the container encoder tag is Lavf 60.3"
    INFERENCE = "INFERENCE"        # concluded from observations, e.g. "consistent with re-encoding"
    INCONCLUSIVE = "INCONCLUSIVE"  # the method ran but cannot decide


class ScoreKind(StrEnum):
    METHOD_SPECIFIC = "METHOD_SPECIFIC"                # a detector's raw output; not a probability
    DISTANCE = "DISTANCE"                              # e.g. Hamming distance between perceptual hashes (lower = closer)
    SIMILARITY = "SIMILARITY"                          # e.g. cosine similarity (higher = closer)
    CALIBRATED_PROBABILITY = "CALIBRATED_PROBABILITY"  # calibrated on stated data; the only kind that allows `confidence`


assert {a.value for a in Assertion} == set(ASSERTIONS)
assert {k.value for k in ScoreKind} == set(SCORE_KINDS)


class TimeRange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self):
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must not be before start_seconds")
        return self


class Region(BaseModel):
    """A rectangle in percent of the analysed image or frame (origin top-left), so it holds at any display size."""

    model_config = ConfigDict(extra="forbid")
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    w: float = Field(gt=0, le=100)
    h: float = Field(gt=0, le=100)
    frame_seconds: float | None = Field(default=None, ge=0, description="For video: the frame the region belongs to")

    @model_validator(mode="after")
    def _inside(self):
        if self.x + self.w > 100.0001 or self.y + self.h > 100.0001:
            raise ValueError("region must lie inside the image")
        return self


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    module_id: str = Field(pattern=r"^NEX-[A-Z]{2,3}$")
    evidence_ids: list[uuid.UUID] = Field(min_length=1)
    assertion: Assertion
    finding_type: str = Field(min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$", examples=["TEMPORAL_DISCONTINUITY"])
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    measurement: dict[str, Any] = Field(default_factory=dict, description="The observed values, in the module's own units")
    score: float | None = None
    score_kind: ScoreKind | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_basis: str | None = Field(default=None, max_length=1000)
    time_range: TimeRange | None = None
    region: Region | None = None
    supporting_artifact_ids: list[uuid.UUID] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _honest_numbers(self):
        if (self.score is None) != (self.score_kind is None):
            raise ValueError("score and score_kind go together: give both or neither")
        if self.confidence is not None:
            if self.score_kind is not ScoreKind.CALIBRATED_PROBABILITY or not self.confidence_basis:
                raise ValueError("confidence requires a CALIBRATED_PROBABILITY score and a stated confidence_basis")
        elif self.confidence_basis:
            raise ValueError("confidence_basis without a confidence value")
        return self
