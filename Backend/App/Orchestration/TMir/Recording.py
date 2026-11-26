"""Writing executions, result envelopes, findings and their outbox events.

Every execution that ends, however it ends, gets exactly one result envelope (Flowchart B §5.2): a completed
run with findings, a skip with its reason, an unavailable module, a failure with its error. These functions
add to the caller's transaction; T-MIR commits them together with the plan update, fenced on the job lease.
"""

import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from Backend.App.Contracts.Artifacts import ArtifactRef, InputReference
from Backend.App.Contracts.ExecutionStates import ExecutionState, FailureReason, ScopeKind
from Backend.App.Contracts.Findings import Finding
from Backend.App.Contracts.ModuleResult import DependencyUse, ModuleError, ModuleResult
from Backend.App.Realtime import Outbox
from Database.PostgreSQL.Models import AnalysisExecution, AnalysisFinding, AnalysisJob, AnalysisResult


def _now() -> datetime:
    return datetime.now(timezone.utc)


def module_event(session: Session, job: AnalysisJob, entry: dict[str, Any], suffix: str, **payload: Any) -> None:
    Outbox.publish(
        session, f"analysis.module.{suffix}", aggregate_type="execution",
        aggregate_id=uuid.UUID(payload.get("execution_id") or str(job.id)),
        case_id=job.case_id, job_id=job.id, module_id=entry["module_id"],
        payload={"job_number": job.display_number, "scope_kind": entry["scope_kind"], "scope_ref": entry["scope_ref"],
                 "evidence_id": entry["evidence_id"]} | payload,
    )


def next_attempt(session: Session, job_id: uuid.UUID, module_id: str, scope_ref: str) -> int:
    current = session.scalar(
        select(func.max(AnalysisExecution.attempt)).where(
            AnalysisExecution.job_id == job_id, AnalysisExecution.module_id == module_id, AnalysisExecution.scope_ref == scope_ref
        )
    )
    return (current or 0) + 1


def open_execution(
    session: Session, job: AnalysisJob, entry: dict[str, Any], *, fingerprint: str, module_version: str,
    parameters: dict[str, Any], running: bool,
) -> AnalysisExecution:
    execution = AnalysisExecution(
        job_id=job.id,
        case_id=job.case_id,
        module_id=entry["module_id"],
        scope_kind=entry["scope_kind"],
        scope_ref=entry["scope_ref"],
        attempt=next_attempt(session, job.id, entry["module_id"], entry["scope_ref"]),
        state=ExecutionState.RUNNING.value if running else ExecutionState.PENDING.value,
        input_fingerprint=fingerprint,
        module_version=module_version,
        parameters=parameters,
        tool_versions={},
        started_at=_now() if running else None,
    )
    session.add(execution)
    session.flush()
    return execution


def close_execution(
    session: Session,
    job: AnalysisJob,
    entry: dict[str, Any],
    execution: AnalysisExecution,
    *,
    status: ExecutionState,
    reason: str | None,
    detail: str | None = None,
    evidence_ids: list[uuid.UUID],
    inputs: list[InputReference] | None = None,
    findings: list[Finding] | None = None,
    dependencies: list[DependencyUse] | None = None,
    limitations: list[str] | None = None,
    warnings: list[str] | None = None,
    errors: list[ModuleError] | None = None,
    tool_versions: dict[str, str] | None = None,
    artifacts: list[ArtifactRef] | None = None,
    related_evidence: list[uuid.UUID] | None = None,
) -> AnalysisResult:
    finished = _now()
    started = execution.started_at
    duration = int((finished - started).total_seconds() * 1000) if started else None
    execution.state = status.value
    execution.state_reason = reason
    execution.state_detail = detail
    execution.finished_at = finished
    execution.duration_ms = duration
    execution.tool_versions = tool_versions or {}
    execution.error = {"errors": [e.model_dump() for e in errors]} if errors else None

    envelope = ModuleResult(
        module_id=execution.module_id,
        module_version=execution.module_version,
        case_id=job.case_id,
        evidence_ids=evidence_ids,
        scope_kind=ScopeKind(execution.scope_kind),
        job_id=job.id,
        execution_id=execution.id,
        status=status,
        status_reason=reason,
        input_references=inputs or [],
        findings=findings or [],
        limitations=limitations or [],
        warnings=warnings or [],
        artifacts=artifacts or [],
        related_evidence=related_evidence or [],
        dependencies=dependencies or [],
        tool_versions=tool_versions or {},
        parameters=execution.parameters,
        started_at=started,
        completed_at=finished,
        execution_time_ms=duration,
        errors=errors or [],
    )
    result = AnalysisResult(
        execution_id=execution.id, job_id=job.id, case_id=job.case_id, module_id=execution.module_id,
        schema_version=envelope.schema_version, status=status.value, envelope=envelope.model_dump(mode="json"),
    )
    session.add(result)
    session.flush()
    for f in envelope.findings:
        session.add(AnalysisFinding(
            id=f.finding_id, result_id=result.id, case_id=job.case_id, module_id=f.module_id, evidence_ids=f.evidence_ids,
            assertion=f.assertion.value, finding_type=f.finding_type, title=f.title, description=f.description,
            score=f.score, score_kind=f.score_kind.value if f.score_kind else None, confidence=f.confidence,
            confidence_basis=f.confidence_basis, payload=f.model_dump(mode="json"),
        ))
    module_event(session, job, entry, status.value.lower(), execution_id=str(execution.id), result_id=str(result.id),
                 state=status.value, reason=reason, detail=detail, attempt=execution.attempt, duration_ms=duration,
                 findings=len(envelope.findings))
    return result


def find_entry(plan: dict[str, Any], key: str) -> dict[str, Any]:
    for e in plan["entries"]:
        if e["key"] == key:
            return e
    raise KeyError(key)


def interrupt(session: Session, job: AnalysisJob, execution: AnalysisExecution, reason: FailureReason, detail: str) -> None:
    """Recovery after a crash: the RUNNING execution becomes FAILED (with its envelope) and its plan entry goes back
    to PENDING, so the next attempt runs that module again as a new execution."""
    plan = copy.deepcopy(job.plan) if job.plan else None
    entry = find_entry(plan, f"{execution.module_id}@{execution.scope_ref}") if plan else {
        "module_id": execution.module_id, "scope_kind": execution.scope_kind, "scope_ref": execution.scope_ref, "evidence_id": None}
    evidence_ids = [uuid.UUID(entry["evidence_id"])] if entry.get("evidence_id") else []
    close_execution(
        session, job, entry, execution, status=ExecutionState.FAILED, reason=reason.value, detail=detail,
        evidence_ids=evidence_ids, errors=[ModuleError(code=reason.value, message=detail, retryable=True)],
    )
    if plan:
        entry["state"] = ExecutionState.PENDING.value
        entry["attempts"] = entry.get("attempts", []) + [str(execution.id)]
        entry["running_execution_id"] = None
        job.plan = plan
