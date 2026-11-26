"""The T-MIR runner: executes one INVESTIGATION_RUN job's plan inside a worker.

For each plan entry, in topological order:

  1. stop if the lease was lost, the job was cancelled, or the job ran out of time;
  2. `decide()` from the registry, using the states of the entry's upstream entries
     (an evidence-scoped upstream of a case-scoped module is aggregated over the run's evidence);
  3. SKIP          -> an execution ending SKIPPED with the decision's reason;
     no executor   -> an execution ending UNAVAILABLE / MODULE_NOT_IMPLEMENTED;
     RUN           -> compute the input fingerprint; if a COMPLETED execution with the same module, scope and
                      fingerprint exists, reuse its result (no new work); otherwise open a RUNNING execution,
                      run the module under the module timeout with no transaction held, then record the
                      module's domain rows, the execution's end, its result envelope, its findings, the plan
                      update and the outbox events in ONE transaction.

Every transaction is fenced on the job lease (JobService.fence), so a worker that lost its lease cannot write.
Because an entry's completion and the module's own records commit together, a crash at any point either
left nothing (the entry runs again on the next attempt) or left everything (the entry is already COMPLETED):
there is never a duplicate COMPLETED execution, and the partial unique index would refuse one anyway.
"""

import copy
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from Backend.App.Config import Settings
from Backend.App.Contracts.ExecutionStates import ExecutionState, FailureReason, JobState, SkipReason
from Backend.App.Contracts.ModuleResult import DependencyUse, ModuleError, input_fingerprint
from Backend.App.Orchestration.TMir import DependencyRegistry as R
from Backend.App.Orchestration.TMir import Planner, Recording
from Backend.App.Orchestration.TMir.Executors import EXECUTORS, NOT_IMPLEMENTED, ExecutionContext, ModuleExecutor, Outcome, default_inputs
from Backend.App.Storage.StorageInterface import EvidenceStorage
from Backend.App.Workers import JobService
from Database.PostgreSQL.Models import AnalysisExecution, AnalysisJob, AnalysisResult, Evidence, MediaRelationship

logger = logging.getLogger("nextron.tmir")

NOT_IMPLEMENTED_VERSION = "not-implemented"
_PLANNED_STEP = {  # where each unbuilt module is scheduled in the approved plan
    "NEX-IMG": 4, "NEX-VID": 4, "NEX-AUD": 4, "NEX-PRV": 4, "NEX-FPM": 5, "NEX-MOC": 5,  # (built; kept for history)
    "NEX-ALN": 6, "NEX-TRN": 6, "NEX-CMC": 6, "NEX-EGC": 7, "NEX-REC": 7,
}


class LeaseLost(Exception):
    """Another worker or the recovery owns the job now; this worker must stop without writing."""


@dataclass
class RunControl:
    worker_id: str
    cancel: threading.Event = field(default_factory=threading.Event)
    lease_lost: threading.Event = field(default_factory=threading.Event)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── upstream state for one entry ─────────────────────────────────────────────────────────────

def _aggregate(entries: list[dict[str, Any]]) -> ExecutionState | None:
    states = [ExecutionState(e["state"]) for e in entries]
    if any(not s.terminal for s in states):
        return None
    if any(s is ExecutionState.COMPLETED for s in states):
        return ExecutionState.COMPLETED
    if any(s is ExecutionState.PARTIALLY_COMPLETED for s in states):
        return ExecutionState.PARTIALLY_COMPLETED
    for s in (ExecutionState.FAILED, ExecutionState.CANCELLED, ExecutionState.UNAVAILABLE):
        if s in states:
            return s
    return ExecutionState.SKIPPED


@dataclass
class UpstreamView:
    states: dict[str, ExecutionState | None] = field(default_factory=dict)
    applicable: dict[str, bool] = field(default_factory=dict)
    results: dict[str, list[uuid.UUID]] = field(default_factory=dict)
    dependencies: list[DependencyUse] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


def upstream_view(plan: dict[str, Any], entry: dict[str, Any]) -> UpstreamView:
    view = UpstreamView()
    for edge in R.upstream_edges(entry["module_id"]):
        u = edge.upstream
        us = R.spec(u)
        if us.owner is R.Owner.DOMAIN_SERVICE:  # CM, CAP, EVD: the evidence record exists, so they completed
            view.states[u] = ExecutionState.COMPLETED
            view.dependencies.append(DependencyUse(module_id=u, edge=edge.kind.value, upstream_state=ExecutionState.COMPLETED))
            continue
        rel = [x for x in plan["entries"] if x["module_id"] == u]
        if us.scope is R.Scope.EVIDENCE and entry["scope_kind"] == "EVIDENCE":
            rel = [x for x in rel if x["scope_ref"] == entry["scope_ref"]]
        if us.owner is not R.Owner.TMIR or not rel:  # SRC, INV, RPT: not part of an investigation run
            view.dependencies.append(DependencyUse(module_id=u, edge=edge.kind.value, upstream_state=None))
            continue
        applicable = [x for x in rel if x["applicable"]]
        view.applicable[u] = bool(applicable)
        state = _aggregate(rel)
        view.states[u] = state
        ids = [uuid.UUID(x["result_id"]) for x in rel if x["result_id"] and ExecutionState(x["state"]).produced_output]
        if ids:
            view.results[u] = ids
        missing = [x for x in applicable if ExecutionState(x["state"]).terminal and not ExecutionState(x["state"]).produced_output]
        if ids and missing:
            view.limitations.append(f"{u} produced no output for {len(missing)} of {len(applicable)} evidence items")
        view.dependencies.append(DependencyUse(module_id=u, edge=edge.kind.value, upstream_state=state, result_id=ids[0] if len(ids) == 1 else None))
    return view


# ── running a module with a time limit ───────────────────────────────────────────────────────

def run_with_timeout(fn: Callable[[], Outcome], seconds: float) -> Outcome:
    """Runs fn in a daemon thread. On timeout the run is abandoned (its thread may still finish, but nothing it
    returns is used or written) and the execution fails with TIMEOUT. Exceptions become FAILED / ERROR."""
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["outcome"] = fn()
        except Exception as exc:  # the module's own failure, recorded on its execution
            logger.exception("Module run raised")
            box["error"] = exc

    thread = threading.Thread(target=target, name="tmir-module", daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        return Outcome(ExecutionState.FAILED, FailureReason.TIMEOUT.value, f"The module did not finish within {seconds:g} s",
                       errors=[ModuleError(code=FailureReason.TIMEOUT.value, message=f"Exceeded the module timeout of {seconds:g} s", retryable=True)])
    if "error" in box:
        exc = box["error"]
        return Outcome(ExecutionState.FAILED, FailureReason.ERROR.value, f"{type(exc).__name__}: {exc}"[:2000],
                       errors=[ModuleError(code=FailureReason.ERROR.value, message=f"{type(exc).__name__}: {exc}"[:2000])])
    return box["outcome"]


# ── the runner ───────────────────────────────────────────────────────────────────────────────

class Runner:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        storage: EvidenceStorage,
        settings: Settings,
        control: RunControl,
        *,
        actor: str,
        executors: dict[str, ModuleExecutor] | None = None,
    ):
        self.factory = session_factory
        self.storage = storage
        self.settings = settings
        self.control = control
        self.actor = actor
        self.executors = EXECUTORS if executors is None else executors

    # Each transaction: copy the plan, change the copy, fence + write + commit; keep the copy only on success.
    def _transaction(self, session: Session, job: AnalysisJob, plan: dict, write: Callable[[Session, dict], None], current: str | None = None) -> dict:
        new_plan = copy.deepcopy(plan)
        try:
            write(session, new_plan)
            if not JobService.fence(session, job.id, self.control.worker_id, plan=new_plan, progress=Planner.progress(new_plan, current)):
                raise LeaseLost()
            session.commit()
        except BaseException:
            session.rollback()
            raise
        return new_plan

    def run(self, job_id: uuid.UUID) -> JobState | None:
        """Runs the job to an end state. Returns it, or None if the lease was lost (nothing more was written)."""
        with self.factory() as session:
            job = session.get(AnalysisJob, job_id)
            try:
                return self._run(session, job)
            except LeaseLost:
                logger.warning("Lease on %s lost; stopping without further writes", job.display_number)
                return None

    def _run(self, session: Session, job: AnalysisJob) -> JobState | None:
        plan = job.plan
        if not plan:
            fresh = Planner.build_plan(session, job)
            plan = self._transaction(session, job, fresh, lambda s, p: None)
        evidence = {str(e.id): e for e in Planner.run_evidence(session, job)}
        session.commit()  # end the read transaction: nothing is held open while modules run
        deadline = (job.started_at or _now()) + timedelta(seconds=job.timeout_seconds)

        for index, entry in enumerate(plan["entries"]):
            if ExecutionState(entry["state"]).terminal:
                continue  # finished in an earlier attempt of this job
            if self.control.lease_lost.is_set():
                raise LeaseLost()
            if self.control.cancel.is_set() or self._cancel_requested(session, job):
                return self._stop(session, job, plan, JobState.CANCELLED, SkipReason.CANCELLED.value,
                                  "The job was cancelled before this module started", None)
            if _now() > deadline:
                return self._stop(session, job, plan, JobState.FAILED, "JOB_TIMEOUT",
                                  f"The job exceeded its time limit of {job.timeout_seconds} s before this module started",
                                  {"code": FailureReason.TIMEOUT.value, "message": f"Exceeded the job time limit of {job.timeout_seconds} s"})
            plan = self._entry(session, job, plan, entry["key"], evidence)

        final = final_state(plan)
        if not JobService.finish(session, job, self.control.worker_id, final, plan=plan, progress=Planner.progress(plan)):
            raise LeaseLost()
        return final

    def _cancel_requested(self, session: Session, job: AnalysisJob) -> bool:
        flag = session.scalar(select(AnalysisJob.cancel_requested).where(AnalysisJob.id == job.id))
        session.commit()
        return bool(flag)

    def _stop(self, session, job, plan, state: JobState, reason: str, detail: str, error: dict | None) -> JobState:
        def write(s: Session, p: dict) -> None:
            for e in p["entries"]:
                if ExecutionState(e["state"]).terminal:
                    continue
                # inputs were never resolved for an entry that did not start, so its fingerprint is the all-zero marker
                ex = Recording.open_execution(s, job, e, fingerprint="0" * 64, module_version=self._version(e["module_id"]), parameters={}, running=False)
                Recording.close_execution(s, job, e, ex, status=ExecutionState.CANCELLED, reason=reason, detail=detail,
                                          evidence_ids=[uuid.UUID(e["evidence_id"])] if e["evidence_id"] else [])
                e.update(state=ExecutionState.CANCELLED.value, reason=reason, detail=detail, execution_id=str(ex.id))
        plan = self._transaction(session, job, plan, write)
        if not JobService.finish(session, job, self.control.worker_id, state, plan=plan, progress=Planner.progress(plan), error=error):
            raise LeaseLost()
        return state

    def _version(self, module_id: str) -> str:
        executor = self.executors.get(module_id)
        return executor.version if executor else NOT_IMPLEMENTED_VERSION

    def _entry(self, session: Session, job: AnalysisJob, plan: dict, key: str, evidence: dict[str, Evidence]) -> dict:
        entry = Recording.find_entry(plan, key)
        module_id = entry["module_id"]
        view = upstream_view(plan, entry)
        decision = R.decide(module_id, applicable=entry["applicable"], upstream=view.states, upstream_applicable=view.applicable)
        if decision.action is R.Action.WAIT:
            raise RuntimeError(f"{key} is waiting on {decision.waiting_on}: the plan is not in dependency order")

        executor = self.executors.get(module_id)
        ev = evidence.get(entry["evidence_id"]) if entry["evidence_id"] else None
        ctx = ExecutionContext(job=job, entry=entry, evidence=ev, run_evidence=list(evidence.values()),
                               upstream_results={u: ids for u, ids in view.results.items() if u in decision.using},
                               settings=self.settings, storage=self.storage, actor=self.actor)
        version = executor.version if executor else NOT_IMPLEMENTED_VERSION
        parameters = executor.parameters(ctx) if executor else {}
        inputs = executor.inputs(ctx) if executor else default_inputs(ctx)
        fingerprint = input_fingerprint(module_id, version, parameters, inputs)
        evidence_ids = [ev.id] if ev else [e.id for e in evidence.values()]
        limitations = decision.limitations + view.limitations

        def end_now(state: ExecutionState, reason: str, detail: str | None):
            def write(s: Session, p: dict) -> None:
                e = Recording.find_entry(p, key)
                ex = Recording.open_execution(s, job, e, fingerprint=fingerprint, module_version=version, parameters=parameters, running=False)
                Recording.close_execution(s, job, e, ex, status=state, reason=reason, detail=detail, evidence_ids=evidence_ids,
                                          inputs=inputs, dependencies=view.dependencies, limitations=limitations)
                e.update(state=state.value, reason=reason, detail=detail, execution_id=str(ex.id), limitations=limitations)
            return self._transaction(session, job, plan, write)

        if decision.action is R.Action.SKIP:
            return end_now(ExecutionState.SKIPPED, decision.reason.value, "; ".join(limitations) or None)
        if R.spec(module_id).scope is R.Scope.PAIR and not self._proposed_pairs(session, job.case_id):
            return end_now(ExecutionState.SKIPPED, SkipReason.NO_INPUT.value, "NEX-MOC proposed no pairs of related evidence to compare")
        if executor is None:
            step = _PLANNED_STEP.get(module_id)
            return end_now(ExecutionState.UNAVAILABLE, NOT_IMPLEMENTED,
                           f"{module_id} ({R.spec(module_id).name}) is not built yet" + (f"; it is planned for Step {step}" if step else ""))

        reusable = self._reusable(session, module_id, entry["scope_ref"], fingerprint)
        if reusable is not None:
            return self._reuse(session, job, plan, key, reusable)

        # open the execution, then run with no transaction held
        opened: dict[str, uuid.UUID] = {}

        def start(s: Session, p: dict) -> None:
            e = Recording.find_entry(p, key)
            ex = Recording.open_execution(s, job, e, fingerprint=fingerprint, module_version=version, parameters=parameters, running=True)
            opened["id"] = ex.id
            ctx.execution_id = ex.id
            e.update(state=ExecutionState.RUNNING.value, running_execution_id=str(ex.id))
            Recording.module_event(s, job, e, "started", execution_id=str(ex.id), attempt=ex.attempt)
        plan = self._transaction(session, job, plan, start, current=module_id)

        outcome = run_with_timeout(lambda: executor.run(ctx), self.settings.MODULE_TIMEOUT_SECONDS)
        if self.control.lease_lost.is_set():
            raise LeaseLost()

        def finish(s: Session, p: dict, record: bool) -> None:
            outcome.artifacts.clear()  # a retried recording must not list artifacts twice
            outcome.related.clear()
            e = Recording.find_entry(p, key)
            ex = s.get(AnalysisExecution, opened["id"])
            findings = executor.record(s, ctx, outcome) if record else []
            result = Recording.close_execution(
                s, job, e, ex, status=outcome.status, reason=outcome.reason, detail=outcome.detail, evidence_ids=evidence_ids,
                inputs=inputs, findings=findings, dependencies=view.dependencies, limitations=limitations + outcome.limitations,
                warnings=outcome.warnings, errors=outcome.errors, tool_versions=outcome.tool_versions, artifacts=outcome.artifacts,
                related_evidence=outcome.related,
            )
            e.update(state=outcome.status.value, reason=outcome.reason, detail=outcome.detail, execution_id=str(ex.id),
                     result_id=str(result.id) if outcome.status.produced_output else None, running_execution_id=None,
                     limitations=limitations + outcome.limitations)

        recordable = outcome.data is not None  # timeouts and crashes inside run() carry no data to record
        try:
            return self._transaction(session, job, plan, lambda s, p: finish(s, p, recordable))
        except IntegrityError:
            # an identical execution completed concurrently in another job: use its result, keep ours as superseded
            existing = self._reusable(session, module_id, entry["scope_ref"], fingerprint)
            if existing is None:
                raise
            return self._supersede(session, job, plan, key, opened["id"], existing)
        except LeaseLost:
            raise
        except Exception as exc:
            if not recordable:
                raise
            logger.exception("Recording %s failed", key)
            outcome = Outcome(ExecutionState.FAILED, FailureReason.ERROR.value, f"Recording the result failed: {type(exc).__name__}",
                              errors=[ModuleError(code="RECORD_FAILED", message=f"{type(exc).__name__}: {exc}"[:2000])])
            return self._transaction(session, job, plan, lambda s, p: finish(s, p, False))

    def _proposed_pairs(self, session: Session, case_id: uuid.UUID) -> int:
        count = session.scalar(select(func.count()).select_from(MediaRelationship).where(
            MediaRelationship.case_id == case_id, MediaRelationship.superseded_at.is_(None))) or 0
        session.commit()
        return count

    def _reusable(self, session: Session, module_id: str, scope_ref: str, fingerprint: str) -> tuple[AnalysisExecution, AnalysisResult] | None:
        row = session.execute(
            select(AnalysisExecution, AnalysisResult)
            .join(AnalysisResult, AnalysisResult.execution_id == AnalysisExecution.id)
            .where(AnalysisExecution.module_id == module_id, AnalysisExecution.scope_ref == scope_ref,
                   AnalysisExecution.input_fingerprint == fingerprint, AnalysisExecution.state == ExecutionState.COMPLETED.value,
                   AnalysisResult.superseded_at.is_(None))
        ).first()
        session.commit()
        return (row[0], row[1]) if row else None

    def _reuse(self, session, job, plan, key, found) -> dict:
        execution, result = found

        def write(s: Session, p: dict) -> None:
            e = Recording.find_entry(p, key)
            e.update(state=ExecutionState.COMPLETED.value, reason="REUSED", execution_id=None, result_id=str(result.id),
                     reused_from_job_id=str(execution.job_id),
                     detail=f"Identical inputs already analysed by this module version (execution {execution.id})")
            Recording.module_event(s, job, e, "reused", execution_id=str(execution.id), result_id=str(result.id),
                                   state=ExecutionState.COMPLETED.value, reused_from_job_id=str(execution.job_id))
        return self._transaction(session, job, plan, write)

    def _supersede(self, session, job, plan, key, execution_id: uuid.UUID, found) -> dict:
        execution, result = found

        def write(s: Session, p: dict) -> None:
            e = Recording.find_entry(p, key)
            ours = s.get(AnalysisExecution, execution_id)
            Recording.close_execution(s, job, e, ours, status=ExecutionState.SKIPPED, reason=SkipReason.SUPERSEDED.value,
                                      detail=f"An identical execution ({execution.id}) completed concurrently; its result is used",
                                      evidence_ids=[uuid.UUID(e["evidence_id"])] if e["evidence_id"] else [])
            e.update(state=ExecutionState.COMPLETED.value, reason="REUSED", execution_id=str(ours.id), result_id=str(result.id),
                     reused_from_job_id=str(execution.job_id), running_execution_id=None,
                     detail=f"Identical inputs analysed concurrently (execution {execution.id})")
        return self._transaction(session, job, plan, write)


def final_state(plan: dict) -> JobState:
    states = [ExecutionState(e["state"]) for e in plan["entries"]]
    if all(s in (ExecutionState.COMPLETED, ExecutionState.SKIPPED) for s in states):
        return JobState.COMPLETED
    if not any(s.produced_output for s in states) and ExecutionState.FAILED in states:
        return JobState.FAILED
    return JobState.PARTIALLY_COMPLETED

