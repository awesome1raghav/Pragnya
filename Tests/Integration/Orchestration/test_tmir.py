"""Step 3: T-MIR runs, the Job Service (claims, leases, recovery, cancel, retry, timeouts), outbox, WebSocket,
notifications and a real worker process. Each test gets its own freshly migrated database, so queued jobs from one
test are never claimed by another."""

import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from starlette.websockets import WebSocketDisconnect

from Backend.App.Contracts.ExecutionStates import ExecutionState, JobState, JobType
from Backend.App.Contracts.ModuleResult import ModuleResult
from Backend.App.Orchestration.TMir.Executors import EXECUTORS, MetadataExecutor, Outcome
from Backend.App.Orchestration.TMir.Runner import RunControl, Runner
from Backend.App.Realtime.Notifications import NotificationConsumer
from Backend.App.Workers import JobService
from Database.PostgreSQL.Models import AnalysisExecution, AnalysisJob, AnalysisResult, EvidenceMetadata, OutboxEvent
from Tests.conftest import alembic_config, build_app, make_worker, run_worker

pytestmark = pytest.mark.postgres
API = "/api/v1"
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def fresh(database_factory, tmp_path):
    """(url, storage_root) of a new, migrated database."""
    _, url = database_factory()
    command.upgrade(alembic_config(url), "head")
    return url, tmp_path / "storage"


@pytest.fixture()
def api(fresh):
    with TestClient(build_app(fresh[0], fresh[1], JOB_RETRY_BASE_SECONDS=0)) as client:
        yield client


def new_case(client) -> str:
    return client.post(f"{API}/cases", json={"title": "T-MIR test case"}).json()["data"]["case_id"]


def upload(client, case_id, data, name, mime) -> dict:
    response = client.post(f"{API}/cases/{case_id}/evidence", files={"file": (name, data, mime)})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def plan_states(client, job_id) -> dict[str, tuple[str, str | None]]:
    run = client.get(f"{API}/runs/{job_id}").json()["data"]
    return {e["module_id"]: (e["state"], e["reason"]) for e in run["plan"]}


def db(client):
    return client.app.state.session_factory()


class Crash(BaseException):
    """Stands in for the worker process dying: nothing after it runs, nothing catches it."""


class CrashWhileRecording(MetadataExecutor):
    """Runs the real extraction, then 'dies' before the completing transaction commits."""

    def record(self, session, ctx, outcome):
        raise Crash()


# ── the image-only run: nothing waits, inapplicable modules are skipped with reasons ─────────

def test_image_only_run_ends_with_every_module_explained(api, media):
    evidence = upload(api, new_case(api), media["png"], "photo.png", "image/png")
    job_id = evidence["analysis_job"]["job_id"]
    assert api.get(f"{API}/jobs/{job_id}").json()["data"]["state"] == "QUEUED"

    assert run_worker(api.app) == [uuid.UUID(job_id)]
    job = api.get(f"{API}/jobs/{job_id}").json()["data"]
    assert job["state"] == "PARTIALLY_COMPLETED"  # detectors are disabled in tests
    assert job["progress"]["finished"] == job["progress"]["planned"] == 12

    states = plan_states(api, job_id)
    assert states == {
        "NEX-MET": ("COMPLETED", None),
        "NEX-IMG": ("PARTIALLY_COMPLETED", "DETECTOR_DISABLED"),  # detectors off in tests
        "NEX-VID": ("SKIPPED", "NOT_APPLICABLE"),
        "NEX-AUD": ("SKIPPED", "NOT_APPLICABLE"),
        "NEX-PRV": ("COMPLETED", None),
        "NEX-FPM": ("COMPLETED", None),
        "NEX-MOC": ("COMPLETED", None),  # one image: nothing to relate, which MOC reports
        "NEX-ALN": ("SKIPPED", "NO_INPUT"),  # MOC proposed no pairs
        "NEX-TRN": ("SKIPPED", "NO_INPUT"),
        "NEX-CMC": ("COMPLETED", None),
        "NEX-EGC": ("COMPLETED", None),
        "NEX-REC": ("COMPLETED", None),  # a timeline of one received item
    }

    run = api.get(f"{API}/runs/{job_id}").json()["data"]
    assert len(run["executions"]) == 12 and all(e["result_id"] for e in run["executions"])
    with db(api) as session:  # every execution has exactly one envelope, and each one is a valid ModuleResult
        results = session.scalars(select(AnalysisResult).where(AnalysisResult.job_id == uuid.UUID(job_id))).all()
        assert len(results) == 12
        for r in results:
            ModuleResult.model_validate(r.envelope)

    analysis = api.get(f"{API}/evidence/{evidence['evidence_id']}/analysis").json()["data"]
    modules = {m["module_id"]: m for m in analysis["modules"]}
    assert list(modules) == ["NEX-MET", "NEX-IMG", "NEX-VID", "NEX-AUD", "NEX-PRV", "NEX-FPM"]
    assert modules["NEX-VID"]["applicable"] is False and modules["NEX-VID"]["latest"]["state"] == "SKIPPED"
    met_result = modules["NEX-MET"]["current_result_id"]
    types = {f["finding_type"] for f in analysis["findings"]}
    assert {"METADATA_RECORDED", "ELA_UNIFORM_RESPONSE", "PERCEPTUAL_HASHES", "NO_CONTENT_CREDENTIALS"} <= types
    assert all(f["confidence"] is None for f in analysis["findings"])  # nothing here is calibrated

    envelope = api.get(f"{API}/analyses/{met_result}").json()["data"]["envelope"]
    assert envelope["status"] == "COMPLETED" and envelope["input_references"][0]["sha256"] == evidence["sha256"]
    assert {d["module_id"] for d in envelope["dependencies"]} == {"NEX-EVD"}
    repro = api.get(f"{API}/analyses/{met_result}/reproducibility").json()["data"]
    assert repro["module_version"] == "nextron-met/1" and len(repro["input_fingerprint"]) == 64
    assert api.get(f"{API}/analyses/{met_result}/artifacts").json()["data"] == []
    assert api.get(f"{API}/analyses/{uuid.uuid4()}").json()["error"]["code"] == "RESULT_NOT_FOUND"


def test_video_plans_audio_and_audio_plans_no_video(api, media):
    case_id = new_case(api)
    video = upload(api, case_id, media["mp4"], "clip.mp4", "video/mp4")
    audio = upload(api, case_id, media["wav"], "voice.wav", "audio/wav")
    run_worker(api.app)
    v = plan_states(api, video["analysis_job"]["job_id"])
    a = plan_states(api, audio["analysis_job"]["job_id"])
    assert v["NEX-VID"] == ("PARTIALLY_COMPLETED", "DETECTOR_NOT_INSTALLED") and v["NEX-AUD"] == ("PARTIALLY_COMPLETED", "DETECTOR_DISABLED")
    assert v["NEX-IMG"] == ("SKIPPED", "NOT_APPLICABLE")
    assert a["NEX-VID"] == ("SKIPPED", "NOT_APPLICABLE") and a["NEX-AUD"] == ("PARTIALLY_COMPLETED", "DETECTOR_DISABLED")
    assert v["NEX-MET"] == a["NEX-MET"] == ("COMPLETED", None)


# ── 202, reuse by input fingerprint, retry ───────────────────────────────────────────────────

def test_analyze_returns_202_and_identical_work_is_reused(api, media):
    evidence = upload(api, new_case(api), media["jpeg_exif"], "camera.jpg", "image/jpeg")
    run_worker(api.app)

    response = api.post(f"{API}/evidence/{evidence['evidence_id']}/analyze")
    assert response.status_code == 202 and response.json()["data"]["state"] == "QUEUED"
    second = response.json()["data"]["job_id"]
    run_worker(api.app)

    run = api.get(f"{API}/runs/{second}").json()["data"]
    met = next(e for e in run["plan"] if e["module_id"] == "NEX-MET")
    assert (met["state"], met["reason"]) == ("COMPLETED", "REUSED")
    assert met["reused_from_job_id"] == evidence["analysis_job"]["job_id"]
    with db(api) as session:
        completed = session.scalar(select(func.count()).where(AnalysisExecution.module_id == "NEX-MET", AnalysisExecution.state == "COMPLETED"))
        versions = session.scalar(select(func.count()).where(EvidenceMetadata.evidence_id == uuid.UUID(evidence["evidence_id"])))
    assert (completed, versions) == (1, 1)  # the second run did not extract again

    retry = api.post(f"{API}/jobs/{second}/retry")
    assert retry.status_code == 202 and retry.json()["data"]["parameters"]["retry_of"] == second
    assert api.post(f"{API}/jobs/{retry.json()['data']['job_id']}/retry").json()["error"]["code"] == "JOB_NOT_RETRYABLE"  # still queued


def test_run_requests_are_validated(api, media):
    case_id = new_case(api)
    assert api.post(f"{API}/cases/{case_id}/runs", json={}).json()["error"]["code"] == "NO_EVIDENCE"
    assert api.post(f"{API}/cases/{uuid.uuid4()}/runs", json={}).status_code == 404
    evidence = upload(api, case_id, media["png"], "a.png", "image/png")
    other = new_case(api)
    upload(api, other, media["wav"], "b.wav", "audio/wav")
    mismatch = api.post(f"{API}/cases/{other}/runs", json={"evidence_id": evidence["evidence_id"]})
    assert mismatch.status_code == 404
    whole_case = api.post(f"{API}/cases/{case_id}/runs", json={})
    assert whole_case.status_code == 202 and whole_case.json()["data"]["evidence_id"] is None
    assert [r["job_id"] for r in api.get(f"{API}/cases/{case_id}/runs").json()["data"]][0] == whole_case.json()["data"]["job_id"]
    api.post(f"{API}/cases/{case_id}/archive", json={"reason": "done"})
    assert api.post(f"{API}/evidence/{evidence['evidence_id']}/analyze").json()["error"]["code"] == "CASE_ARCHIVED"


# ── claims, leases, fencing, recovery ────────────────────────────────────────────────────────

def _queue(client, n: int) -> list[uuid.UUID]:
    case_id = uuid.UUID(new_case(client))
    with db(client) as session:
        jobs = [JobService.enqueue(session, job_type=JobType.INVESTIGATION_RUN, case_id=case_id, requested_by="test",
                                   settings=client.app.state.settings) for _ in range(n)]
        session.commit()
        return [j.id for j in jobs]


def test_concurrent_claims_never_hand_out_a_job_twice(api):
    queued = set(_queue(api, 30))
    claimed: list[uuid.UUID] = []
    lock = threading.Lock()
    barrier = threading.Barrier(8)

    def claimer(n: int) -> None:
        barrier.wait()
        while True:
            with db(api) as session:
                job = JobService.claim(session, f"claimer-{n}", lease_seconds=60)
            if job is None:
                return
            with lock:
                claimed.append(job.id)

    threads = [threading.Thread(target=claimer, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert len(claimed) == len(set(claimed)) == 30 and set(claimed) == queued
    with db(api) as session:
        rows = session.execute(select(AnalysisJob.state, AnalysisJob.lease_owner, AnalysisJob.attempt)).all()
    assert {r.state for r in rows} == {"RUNNING"} and {r.attempt for r in rows} == {1}
    assert 1 < len({r.lease_owner for r in rows}) <= 8  # spread across claimers, each job held by exactly one


def test_a_worker_that_lost_its_lease_cannot_write(api):
    job_id = _queue(api, 1)[0]
    with db(api) as session:
        job = JobService.claim(session, "worker-a", lease_seconds=60)
        session.execute(text("UPDATE analysis_jobs SET lease_expires_at = now() - interval '1 second' WHERE id = :id"), {"id": job_id})
        session.commit()
        assert JobService.recover_expired(session, api.app.state.settings, close_execution=lambda *a: None) == [job_id]
        again = JobService.claim(session, "worker-b", lease_seconds=60)
        assert again.id == job_id and again.attempt == 2

        assert JobService.heartbeat(session, job_id, "worker-a", lease_seconds=60).lease_held is False
        assert JobService.finish(session, job, "worker-a", JobState.COMPLETED) is False
        assert JobService.heartbeat(session, job_id, "worker-b", lease_seconds=60).lease_held is True
        session.refresh(job)
        assert (job.state, job.lease_owner) == ("RUNNING", "worker-b")


def test_worker_killed_mid_module_is_recovered_without_duplicates(api, media):
    evidence = upload(api, new_case(api), media["png"], "photo.png", "image/png")
    job_id = uuid.UUID(evidence["analysis_job"]["job_id"])

    dying = make_worker(api.app, worker_id="dying-worker", executors=dict(EXECUTORS) | {"NEX-MET": CrashWhileRecording()})
    with pytest.raises(Crash):
        dying.process_one()
    with db(api) as session:
        job = session.get(AnalysisJob, job_id)
        assert (job.state, job.lease_owner) == ("RUNNING", "dying-worker")  # nobody told the database
        running = session.scalars(select(AnalysisExecution).where(AnalysisExecution.job_id == job_id)).all()
        assert [(e.module_id, e.state) for e in running] == [("NEX-MET", "RUNNING")]
        assert session.scalar(select(func.count()).select_from(EvidenceMetadata)) == 0  # rolled back with the result
        session.execute(text("UPDATE analysis_jobs SET lease_expires_at = now() - interval '1 second' WHERE id = :id"), {"id": job_id})
        session.commit()

    assert run_worker(api.app) == [job_id]  # recovers the expired lease, then claims and finishes attempt 2

    with db(api) as session:
        job = session.get(AnalysisJob, job_id)
        assert (job.state, job.attempt) == ("PARTIALLY_COMPLETED", 2)
        mets = session.scalars(select(AnalysisExecution).where(AnalysisExecution.module_id == "NEX-MET").order_by(AnalysisExecution.attempt)).all()
        assert [(e.attempt, e.state, e.state_reason) for e in mets] == [(1, "FAILED", "LEASE_EXPIRED"), (2, "COMPLETED", None)]
        assert session.scalar(select(func.count()).select_from(EvidenceMetadata)) == 1
        executions = session.scalar(select(func.count()).where(AnalysisExecution.job_id == job_id))
        results = session.scalar(select(func.count()).where(AnalysisResult.job_id == job_id))
        assert executions == results == 13  # 12 entries + the interrupted attempt, each with one envelope
        events = [e.event_type for e in session.scalars(select(OutboxEvent).where(OutboxEvent.job_id == job_id).order_by(OutboxEvent.sequence))]
    assert events.count("job.started") == 2 and "job.retry_scheduled" in events and events[-1] == "job.partially_completed"
    entry = next(e for e in api.get(f"{API}/runs/{job_id}").json()["data"]["plan"] if e["module_id"] == "NEX-MET")
    assert entry["interrupted_attempts"] == [str(mets[0].id)]


def test_crash_after_a_module_committed_does_not_rerun_it(api, media):
    class CrashingImageEngine:
        module_id, version = "NEX-IMG", "test-img/1"

        def parameters(self, ctx):
            return {}

        def inputs(self, ctx):
            return MetadataExecutor().inputs(ctx)

        def run(self, ctx):
            return Outcome(ExecutionState.COMPLETED, data=True)

        def record(self, session, ctx, outcome):
            raise Crash()

    evidence = upload(api, new_case(api), media["png"], "photo.png", "image/png")
    job_id = uuid.UUID(evidence["analysis_job"]["job_id"])
    with pytest.raises(Crash):
        make_worker(api.app, executors=dict(EXECUTORS) | {"NEX-IMG": CrashingImageEngine()}).process_one()
    with db(api) as session:
        session.execute(text("UPDATE analysis_jobs SET lease_expires_at = now() - interval '1 second' WHERE id = :id"), {"id": job_id})
        session.commit()
    run_worker(api.app)
    with db(api) as session:
        mets = session.scalars(select(AnalysisExecution).where(AnalysisExecution.module_id == "NEX-MET")).all()
        imgs = session.scalars(select(AnalysisExecution).where(AnalysisExecution.module_id == "NEX-IMG").order_by(AnalysisExecution.attempt)).all()
        assert [(m.attempt, m.state) for m in mets] == [(1, "COMPLETED")]  # committed before the crash; not run again
        assert [(i.attempt, i.state, i.state_reason) for i in imgs] == [(1, "FAILED", "LEASE_EXPIRED"), (2, "PARTIALLY_COMPLETED", "DETECTOR_DISABLED")]
        assert session.scalar(select(func.count()).select_from(EvidenceMetadata)) == 1


def test_database_refuses_a_second_completed_execution_for_the_same_inputs(api, media):
    evidence = upload(api, new_case(api), media["png"], "photo.png", "image/png")
    run_worker(api.app)
    with db(api) as session:
        met = session.scalars(select(AnalysisExecution).where(AnalysisExecution.module_id == "NEX-MET")).one()
        with pytest.raises(Exception, match="uq_analysis_executions_completed_fingerprint"):
            session.execute(text("""INSERT INTO analysis_executions (id, job_id, case_id, module_id, scope_kind, scope_ref, attempt, state,
                input_fingerprint, module_version, parameters, tool_versions, finished_at)
                VALUES (gen_random_uuid(), :job, :case, 'NEX-MET', 'EVIDENCE', :scope, 9, 'COMPLETED', :fp, 'x', '{}', '{}', now())"""),
                                {"job": met.job_id, "case": met.case_id, "scope": met.scope_ref, "fp": met.input_fingerprint})
    assert evidence["evidence_id"] == met.scope_ref


# ── cancel, retry with backoff, timeouts ─────────────────────────────────────────────────────

def test_cancel_queued_and_running_jobs(api, media):
    first, second = _queue(api, 2)
    cancelled = api.post(f"{API}/jobs/{first}/cancel")
    assert cancelled.status_code == 200 and cancelled.json()["data"]["state"] == "CANCELLED"
    assert api.post(f"{API}/jobs/{first}/cancel").json()["error"]["code"] == "JOB_NOT_CANCELLABLE"
    assert api.post(f"{API}/jobs/{uuid.uuid4()}/cancel").json()["error"]["code"] == "JOB_NOT_FOUND"

    evidence = upload(api, new_case(api), media["png"], "p.png", "image/png")
    running_id = uuid.UUID(evidence["analysis_job"]["job_id"])
    with db(api) as session:  # claim the upload's job by hand, then ask for cancellation while it is RUNNING
        while (job := JobService.claim(session, "worker-c", lease_seconds=60)) and job.id != running_id:
            pass
    flagged = api.post(f"{API}/jobs/{running_id}/cancel").json()["data"]
    assert (flagged["state"], flagged["cancel_requested"]) == ("RUNNING", True)
    state = Runner(api.app.state.session_factory, api.app.state.storage, api.app.state.settings, RunControl("worker-c"),
                   actor="test").run(running_id)
    assert state is JobState.CANCELLED
    assert set(plan_states(api, running_id).values()) == {("CANCELLED", "CANCELLED")}
    assert api.get(f"{API}/jobs/{second}").json()["data"]["state"] == "RUNNING"  # claimed by worker-c above, untouched


def test_infrastructure_errors_retry_with_backoff_then_fail(fresh, media):
    class BrokenInputs(MetadataExecutor):
        def inputs(self, ctx):
            raise RuntimeError("input store unreachable")

    with TestClient(build_app(fresh[0], fresh[1], JOB_RETRY_BASE_SECONDS=0, JOB_MAX_ATTEMPTS=2)) as client:
        evidence = upload(client, new_case(client), media["png"], "p.png", "image/png")
        job_id = evidence["analysis_job"]["job_id"]
        broken = dict(EXECUTORS) | {"NEX-MET": BrokenInputs()}
        run_worker(client.app, executors=broken)
        job = client.get(f"{API}/jobs/{job_id}").json()["data"]
        assert (job["state"], job["attempt"], job["error"]["code"]) == ("FAILED", 2, "WORKER_ERROR")
        assert "input store unreachable" in job["error"]["message"]

    with TestClient(build_app(fresh[0], fresh[1], JOB_RETRY_BASE_SECONDS=10, JOB_MAX_ATTEMPTS=3)) as client:
        evidence = upload(client, new_case(client), media["png"], "q.png", "image/png")
        job_id = evidence["analysis_job"]["job_id"]
        make_worker(client.app, executors=broken).process_one()
        job = client.get(f"{API}/jobs/{job_id}").json()["data"]
        assert (job["state"], job["attempt"]) == ("QUEUED", 1)
        with db(client) as session:
            delay = session.scalar(text("SELECT EXTRACT(EPOCH FROM available_at - now()) FROM analysis_jobs WHERE id = :id"), {"id": job_id})
        assert 8 < float(delay) <= 10  # 10 s * 2^(attempt-1)
        assert make_worker(client.app).process_one() is None  # not claimable before the backoff passes


def test_module_timeout_fails_the_module_not_the_worker(fresh, media):
    class SlowMetadata(MetadataExecutor):
        def run(self, ctx):
            time.sleep(3)
            return super().run(ctx)

    with TestClient(build_app(fresh[0], fresh[1], MODULE_TIMEOUT_SECONDS=0.5)) as client:
        evidence = upload(client, new_case(client), media["png"], "p.png", "image/png")
        run_worker(client.app, executors=dict(EXECUTORS) | {"NEX-MET": SlowMetadata()})
        job_id = evidence["analysis_job"]["job_id"]
        assert plan_states(client, job_id)["NEX-MET"] == ("FAILED", "TIMEOUT")
        assert client.get(f"{API}/jobs/{job_id}").json()["data"]["state"] == "PARTIALLY_COMPLETED"  # the image engine still produced output
        with db(client) as session:
            assert session.scalar(select(func.count()).select_from(EvidenceMetadata)) == 0  # the abandoned run wrote nothing


def test_job_time_limit_stops_before_the_next_module(api, media):
    evidence = upload(api, new_case(api), media["png"], "p.png", "image/png")
    job_id = uuid.UUID(evidence["analysis_job"]["job_id"])
    with db(api) as session:
        JobService.claim(session, "worker-t", lease_seconds=60)
        session.execute(text("UPDATE analysis_jobs SET started_at = now() - interval '2 hours' WHERE id = :id"), {"id": job_id})
        session.commit()
    state = Runner(api.app.state.session_factory, api.app.state.storage, api.app.state.settings, RunControl("worker-t"), actor="t").run(job_id)
    job = api.get(f"{API}/jobs/{job_id}").json()["data"]
    assert state is JobState.FAILED and job["error"]["code"] == "TIMEOUT"
    assert set(plan_states(api, job_id).values()) == {("CANCELLED", "JOB_TIMEOUT")}


# ── outbox, WebSocket, notifications, workers ────────────────────────────────────────────────

def test_outbox_records_domain_and_run_events_in_order(api, media):
    case_id = new_case(api)
    evidence = upload(api, case_id, media["png"], "p.png", "image/png")
    api.post(f"{API}/evidence/{evidence['evidence_id']}/verify-integrity")
    run_worker(api.app)
    with db(api) as session:
        events = session.scalars(select(OutboxEvent).where(OutboxEvent.case_id == uuid.UUID(case_id)).order_by(OutboxEvent.sequence)).all()
    types = [e.event_type for e in events]
    assert types[:4] == ["case.created", "evidence.created", "job.queued", "evidence.integrity_match"]
    assert types[4] == "job.started" and types[-1] == "job.partially_completed"
    module_events = [t for t in types if t.startswith("analysis.module.")]
    assert module_events[:2] == ["analysis.module.started", "analysis.module.completed"]  # MET first
    assert len(module_events) == 20  # MET, IMG, PRV, FPM, MOC, CMC, EGC and REC started + 12 endings
    assert module_events.count("analysis.module.started") == 8
    assert [e.sequence for e in events] == sorted(e.sequence for e in events)


def _receive_until(ws, predicate, limit=200):
    seen = []
    for _ in range(limit):
        message = ws.receive_json()
        seen.append(message)
        if predicate(message):
            return seen
    raise AssertionError(f"condition not met in {limit} messages: {[m.get('event_type', m['type']) for m in seen]}")


def test_websocket_replays_then_streams_live_events(api, media):
    case_id = new_case(api)
    evidence = upload(api, case_id, media["png"], "p.png", "image/png")

    with api.websocket_connect(f"{API}/ws/cases/{case_id}?after=0") as ws:
        replay = _receive_until(ws, lambda m: m["type"] == "replay_complete")
        assert [m["event_type"] for m in replay[:-1]] == ["case.created", "evidence.created", "job.queued"]
        first_sequence = replay[0]["sequence"]

        run_worker(api.app)  # events written by the worker reach the socket through the dispatcher
        live = _receive_until(ws, lambda m: m.get("event_type") == "job.partially_completed")
        live_events = [m for m in live if m["type"] == "event"]
        assert live_events[0]["event_type"] == "job.started"
        assert all(m["case_id"] == case_id for m in live_events)
        sequences = [m["sequence"] for m in replay[:-1] + live_events]
        assert len(sequences) == len(set(sequences))  # nothing sent twice

    with api.websocket_connect(f"{API}/ws/jobs/{evidence['analysis_job']['job_id']}?after={first_sequence}") as ws:
        resumed = _receive_until(ws, lambda m: m["type"] == "replay_complete")
        assert resumed[0]["event_type"] == "job.queued" and all(m["sequence"] > first_sequence for m in resumed[:-1])

    with pytest.raises(WebSocketDisconnect) as refused:
        with api.websocket_connect(f"{API}/ws/events", headers={"origin": "http://evil.example"}) as ws:
            ws.receive_json()
    assert refused.value.code == 1008


def test_notifications_are_derived_once_and_can_be_read(api, media):
    evidence = upload(api, new_case(api), media["png"], "p.png", "image/png")
    run_worker(api.app)
    with db(api) as session:
        NotificationConsumer(gap_timeout=0).process(session)
        NotificationConsumer(gap_timeout=0).process(session)  # a second consumer (or a restart) re-reads harmlessly
    items = api.get(f"{API}/notifications").json()["data"]
    mine = [n for n in items if n["job_id"] == evidence["analysis_job"]["job_id"]]
    assert len(mine) == 1 and mine[0]["severity"] == "WARNING" and mine[0]["title"].endswith("completed partially")
    assert mine[0]["link"] == f"/evidence/{evidence['evidence_id']}/analysis"
    assert api.get(f"{API}/notifications/summary").json()["data"]["unread"] == len(items)

    read = api.patch(f"{API}/notifications/{mine[0]['notification_id']}/read").json()["data"]
    assert read["read_at"] is not None
    assert api.post(f"{API}/notifications/read-all").json()["data"]["marked"] == len(items) - 1
    assert api.get(f"{API}/notifications?unread=true").json()["data"] == []
    assert api.patch(f"{API}/notifications/{uuid.uuid4()}/read").json()["error"]["code"] == "NOTIFICATION_NOT_FOUND"


def test_system_workers_reports_heartbeats_honestly(api):
    assert api.get(f"{API}/system/workers").json()["data"]["alive"] == 0
    worker = make_worker(api.app, worker_id="observed-worker")
    status = api.get(f"{API}/system/workers").json()["data"]
    assert status["alive"] == 1 and status["workers"][0]["worker_id"] == "observed-worker"
    worker.deregister()
    status = api.get(f"{API}/system/workers").json()["data"]
    assert status["alive"] == 0 and status["workers"][0]["state"] == "STOPPED"


def test_a_real_worker_process_runs_queued_jobs(fresh, media):
    url, storage = fresh
    with TestClient(build_app(url, storage)) as client:
        evidence = upload(client, new_case(client), media["wav"], "voice.wav", "audio/wav")
        job_id = evidence["analysis_job"]["job_id"]
        env = os.environ | {"DATABASE_URL": url, "STORAGE_ROOT": str(storage), "WORKER_POLL_SECONDS": "0.2", "LOG_LEVEL": "WARNING",
                            "DETECTORS_ENABLED": "false", "NEO4J_URI": ""}  # as build_app: no weights, no shared graph
        process = subprocess.Popen([sys.executable, "-m", "Backend.App.Workers.Worker"], cwd=ROOT, env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                state = client.get(f"{API}/jobs/{job_id}").json()["data"]["state"]
                if state not in ("QUEUED", "RUNNING"):
                    break
                time.sleep(0.3)
            assert state == "PARTIALLY_COMPLETED"
            assert client.get(f"{API}/evidence/{evidence['evidence_id']}/metadata").json()["data"]["extractor"] == "ffprobe"
            workers = client.get(f"{API}/system/workers").json()["data"]
            assert workers["alive"] == 1 and workers["workers"][0]["state"] == "RUNNING"
        finally:
            # A hard kill, like a crash. On Windows the venv python.exe is a launcher with the interpreter as its child,
            # so the whole process tree is killed.
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
            else:
                process.kill()
            output = process.communicate(timeout=10)[0].decode(errors="replace")
        assert "Traceback" not in output, output


def test_cursor_waits_for_gaps_then_skips_them():
    from Backend.App.Realtime.Cursor import GapSafeCursor

    now = [0.0]
    cursor = GapSafeCursor(10, gap_timeout=5, clock=lambda: now[0])
    cursor.mark(12)
    assert cursor.position == 10 and cursor.is_new(11) and not cursor.is_new(12)
    cursor.mark(11)
    assert cursor.position == 12
    cursor.mark(14)
    now[0] = 4.9
    cursor.tick()
    assert cursor.position == 12  # 13 may still commit
    now[0] = 5.1
    cursor.tick()
    assert cursor.position == 14  # 13 was rolled back: skipped


def test_websocket_without_after_starts_live(api, media):
    case_id = new_case(api)
    upload(api, case_id, media["png"], "p.png", "image/png")
    with api.websocket_connect(f"{API}/ws/events") as ws:
        first = ws.receive_json()
        assert first["type"] == "replay_complete"  # nothing from the past is replayed
        with db(api) as session:
            assert first["latest"] <= session.scalar(select(func.max(OutboxEvent.sequence)))
        run_worker(api.app)
        live = [m for m in _receive_until(ws, lambda m: m.get("event_type") == "job.partially_completed") if m["type"] == "event"]
        assert "job.started" in [m["event_type"] for m in live]
        assert all(m["sequence"] > first["after"] for m in live)  # nothing at or before the starting point


def test_engine_artifacts_are_stored_hashed_and_served_inert(api, media, fresh):
    import hashlib
    import os
    case_id = new_case(api)
    evidence = upload(api, case_id, media["mp4"], "clip.mp4", "video/mp4")
    run_worker(api.app)
    results = api.get(f"{API}/cases/{case_id}/modules/NEX-VID/results").json()["data"]
    item = results["evidence"][0]
    assert (item["status"], item["status_reason"]) == ("PARTIALLY_COMPLETED", "DETECTOR_NOT_INSTALLED")
    assert {a["kind"] for a in item["artifacts"]} == {"FRAME_SET", "FINGERPRINT"}
    assert any("deepfake detector" in limit for limit in item["limitations"])
    envelope = api.get(f"{API}/analyses/{item['result_id']}").json()["data"]["envelope"]
    assert {a["artifact_id"] for a in envelope["artifacts"]} == {a["artifact_id"] for a in item["artifacts"]}

    sheet = next(a for a in item["artifacts"] if a["kind"] == "FRAME_SET")
    served = api.get(f"{API}/artifacts/{sheet['artifact_id']}")
    assert served.status_code == 200 and served.headers["content-type"] == "image/png"
    assert served.headers["x-content-type-options"] == "nosniff" and "sandbox" in served.headers["content-security-policy"]
    assert hashlib.sha256(served.content).hexdigest() == sheet["sha256"] == served.headers["x-artifact-sha256"]
    stored = fresh[1] / "Derived" / case_id / evidence["evidence_id"] / f"{sheet['artifact_id']}.png"
    assert stored.is_file() and not os.access(stored, os.W_OK)  # derived files are read-only too

    audio = api.get(f"{API}/cases/{case_id}/modules/NEX-AUD/results").json()["data"]["evidence"][0]
    assert {a["kind"] for a in audio["artifacts"]} == {"HEATMAP", "AUDIO_TRACK"}  # the fixture clip has an AAC track
    assert api.get(f"{API}/artifacts/{uuid.uuid4()}").json()["error"]["code"] == "ARTIFACT_NOT_FOUND"
    assert api.get(f"{API}/cases/{case_id}/modules/NEX-EGC/results").json()["error"]["code"] == "UNKNOWN_MODULE"
