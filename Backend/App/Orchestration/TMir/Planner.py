"""T-MIR execution planning: which module runs for which scope in an investigation run.

The plan is a snapshot stored on the job (`analysis_jobs.plan`) so a retry or a recovered run continues the
same plan, and so the UI can show every module, including those that will not run and why.

* Evidence-scoped modules (MET, IMG, VID, AUD, PRV, FPM) get one entry per evidence item in the run, marked
  applicable or not from the evidence record alone (an image never plans audio forensics).
* Case-scoped modules (MOC, CMC, EGC, REC) get one entry for the case.
* Pair-scoped modules (ALN, TRN) get one placeholder entry, `<case>:pairs`. The pairs themselves come from
  NEX-MOC's lineage proposals; until MOC produces them the placeholder is decided like any other entry
  (with MOC not producing output, it is skipped with NO_INPUT). Expanding it into per-pair entries is Step 6.

Entries are in the registry's topological order, so a sequential runner meets every upstream first.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from Backend.App.Contracts.ExecutionStates import ExecutionState, ScopeKind
from Backend.App.Orchestration.TMir import DependencyRegistry as R
from Database.PostgreSQL.Models import AnalysisJob, Evidence

PLAN_SCHEMA = 1


def facts(evidence: Evidence) -> R.EvidenceFacts:
    return R.EvidenceFacts(media_type=evidence.media_type, mime_type=evidence.mime_type)


def run_evidence(session: Session, job: AnalysisJob) -> list[Evidence]:
    """The evidence a run covers: the one item it was started for, or every item in the case."""
    query = select(Evidence).where(Evidence.case_id == job.case_id)
    if job.evidence_id is not None:
        query = query.where(Evidence.id == job.evidence_id)
    return list(session.scalars(query.order_by(Evidence.evidence_number)))


def _entry(module_id: str, scope_kind: ScopeKind, scope_ref: str, *, evidence_id: uuid.UUID | None, applicable: bool) -> dict[str, Any]:
    return {
        "key": f"{module_id}@{scope_ref}",
        "module_id": module_id,
        "scope_kind": scope_kind.value,
        "scope_ref": scope_ref,
        "evidence_id": str(evidence_id) if evidence_id else None,
        "applicable": applicable,
        "state": ExecutionState.PENDING.value,
        "reason": None,
        "detail": None,
        "execution_id": None,   # this job's execution that ended the entry
        "result_id": None,      # the result downstream modules read (this job's, or a reused one)
        "reused_from_job_id": None,
        "attempts": [],         # executions of earlier attempts interrupted by a crash
        "limitations": [],
    }


def build_plan(session: Session, job: AnalysisJob) -> dict[str, Any]:
    evidence = run_evidence(session, job)
    case_ref = str(job.case_id)
    entries: list[dict[str, Any]] = []
    for module_id in R.topological_order():
        m = R.spec(module_id)
        if m.owner is not R.Owner.TMIR:
            continue
        if m.scope is R.Scope.EVIDENCE:
            for e in evidence:
                entries.append(_entry(module_id, ScopeKind.EVIDENCE, str(e.id), evidence_id=e.id, applicable=R.applies_to(module_id, facts(e))))
        elif m.scope is R.Scope.CASE:
            entries.append(_entry(module_id, ScopeKind.CASE, case_ref, evidence_id=None, applicable=True))
        elif m.scope is R.Scope.PAIR:
            entries.append(_entry(module_id, ScopeKind.PAIR, f"{case_ref}:pairs", evidence_id=None, applicable=True))
    return {
        "schema": PLAN_SCHEMA,
        "case_id": case_ref,
        "evidence_ids": [str(e.id) for e in evidence],
        "registry_edges": len(R.EDGES),
        "entries": entries,
    }


def progress(plan: dict[str, Any], current: str | None = None) -> dict[str, Any]:
    """Measured progress only: how many planned entries have ended, by state."""
    entries = plan["entries"]
    by_state: dict[str, int] = {}
    for e in entries:
        by_state[e["state"]] = by_state.get(e["state"], 0) + 1
    finished = sum(1 for e in entries if ExecutionState(e["state"]).terminal)
    return {"planned": len(entries), "finished": finished, "by_state": by_state, "current": current}
