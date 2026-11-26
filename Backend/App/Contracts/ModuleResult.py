"""The module result envelope (Flowchart B §5.2, schema 1.0), adapted to the persisted model.

Every module execution ends with exactly one of these, whatever happened: a completed run with findings,
a partial run, a failure, a skip because the module did not apply, or "unavailable" because its tool is
missing. Downstream modules trace every finding back through `input_references` to the evidence digests.
"""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from Backend.App.Contracts.Artifacts import ArtifactRef, InputReference
from Backend.App.Contracts.ExecutionStates import ExecutionState, ScopeKind
from Backend.App.Contracts.Findings import Finding

SCHEMA_VERSION = "1.0"


class ModuleError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=2000)
    retryable: bool = False


class DependencyUse(BaseModel):
    """How one upstream module was used by this execution (or why it was not)."""

    model_config = ConfigDict(extra="forbid")
    module_id: str = Field(pattern=r"^NEX-[A-Z]{2,3}$")
    edge: str = Field(pattern=r"^(REQUIRED|CONDITIONAL|OPTIONAL)$")
    upstream_state: ExecutionState | None = Field(description="null when the upstream was not part of this run")
    result_id: uuid.UUID | None = None


class ModuleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    module_id: str = Field(pattern=r"^NEX-[A-Z]{2,3}$")
    module_version: str = Field(min_length=1, max_length=100)
    case_id: uuid.UUID
    evidence_ids: list[uuid.UUID] = Field(default_factory=list)
    scope_kind: ScopeKind
    job_id: uuid.UUID
    execution_id: uuid.UUID
    status: ExecutionState
    status_reason: str | None = Field(default=None, max_length=64, description="Required for SKIPPED, UNAVAILABLE, FAILED, CANCELLED, PARTIALLY_COMPLETED")
    input_references: list[InputReference] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_basis: str | None = None
    limitations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    related_evidence: list[uuid.UUID] = Field(default_factory=list)
    dependencies: list[DependencyUse] = Field(default_factory=list)
    tool_versions: dict[str, str] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    execution_time_ms: int | None = Field(default=None, ge=0)
    errors: list[ModuleError] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self):
        if not self.status.terminal:
            raise ValueError("a result is written only when the execution has ended (terminal status)")
        if self.status.needs_reason and not self.status_reason:
            raise ValueError(f"{self.status} results must give a status_reason")
        if self.findings and not self.status.produced_output:
            raise ValueError("only COMPLETED or PARTIALLY_COMPLETED results may carry findings")
        if self.status is ExecutionState.FAILED and not self.errors:
            raise ValueError("a FAILED result must include at least one error")
        if (self.confidence is None) != (self.confidence_basis is None):
            raise ValueError("result-level confidence needs a stated basis, and a basis needs a value")
        for f in self.findings:
            if f.module_id != self.module_id:
                raise ValueError("every finding must come from this result's module")
            if self.evidence_ids and not set(f.evidence_ids) <= set(self.evidence_ids) | set(self.related_evidence):
                raise ValueError("a finding may only cite evidence this result covers")
        if self.started_at and self.completed_at and self.completed_at < self.started_at:
            raise ValueError("completed_at is before started_at")
        return self


def input_fingerprint(module_id: str, module_version: str, parameters: dict[str, Any], inputs: list[InputReference]) -> str:
    """SHA-256 identifying 'this module version, on exactly these inputs, with these parameters'.

    Two executions with the same fingerprint would compute the same thing, so a completed one can be reused
    (and the database refuses a second COMPLETED row with the same module, scope and fingerprint).
    """
    canonical = {
        "module_id": module_id,
        "module_version": module_version,
        "parameters": parameters,
        "inputs": sorted(
            (ref.kind.value, str(ref.id), ref.module_id or "", ref.sha256 or "", ref.revision or 0) for ref in inputs
        ),
    }
    data = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()
