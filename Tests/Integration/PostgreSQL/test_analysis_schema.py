"""Migration 0004's tables enforce the contract rules in the database itself."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from Database.PostgreSQL.Connection import EngineOptions, create_database_engine

pytestmark = pytest.mark.postgres
FP = "f" * 64


@pytest.fixture()
def db(migrated_database):
    engine = create_database_engine(migrated_database[1], EngineOptions(pooled=False))
    with engine.begin() as c:
        case_id = c.execute(text("INSERT INTO cases (id, title, status, priority, created_by, revision) VALUES (gen_random_uuid(), 'schema test', 'OPEN', 'LOW', 'tester', 1) RETURNING id")).scalar_one()
        job_id = c.execute(text("INSERT INTO analysis_jobs (id, job_type, case_id, state, priority, requested_by, parameters, attempt, max_attempts, timeout_seconds) "
                                "VALUES (gen_random_uuid(), 'INVESTIGATION_RUN', :c, 'QUEUED', 50, 'tester', '{}', 0, 3, 600) RETURNING id"), {"c": case_id}).scalar_one()
    yield engine, case_id, job_id
    engine.dispose()


def execution(c, case_id, job_id, *, module="NEX-MET", state="COMPLETED", reason=None, scope=None, fingerprint=FP, attempt=1):
    finished = "now()" if state in ("COMPLETED", "PARTIALLY_COMPLETED", "FAILED", "CANCELLED", "SKIPPED", "UNAVAILABLE") else "NULL"
    return c.execute(text(
        "INSERT INTO analysis_executions (id, job_id, case_id, module_id, scope_kind, scope_ref, attempt, state, state_reason, input_fingerprint, module_version, parameters, tool_versions, finished_at) "
        f"VALUES (gen_random_uuid(), :j, :c, :m, 'EVIDENCE', :s, :a, :st, :r, :fp, 'test/1', '{{}}', '{{}}', {finished}) RETURNING id"),
        {"j": job_id, "c": case_id, "m": module, "s": scope or str(uuid.uuid4()), "a": attempt, "st": state, "r": reason, "fp": fingerprint}).scalar_one()


def test_skipped_or_failed_executions_must_say_why(db):
    engine, case_id, job_id = db
    with engine.begin() as c, pytest.raises(IntegrityError, match="explained_states_have_reason"):
        execution(c, case_id, job_id, state="SKIPPED")
    with engine.begin() as c:
        execution(c, case_id, job_id, state="SKIPPED", reason="NOT_APPLICABLE")


def test_identical_completed_work_cannot_be_recorded_twice(db):
    engine, case_id, job_id = db
    scope = str(uuid.uuid4())
    with engine.begin() as c:
        execution(c, case_id, job_id, scope=scope, attempt=1)
        execution(c, case_id, job_id, scope=scope, attempt=2, state="FAILED", reason="TIMEOUT")  # failures do not count
    with engine.begin() as c, pytest.raises(IntegrityError, match="uq_analysis_executions_completed_fingerprint"):
        execution(c, case_id, job_id, scope=scope, attempt=3)


def test_running_jobs_hold_a_lease_and_finished_jobs_a_finish_time(db):
    engine, _, job_id = db
    with engine.begin() as c, pytest.raises(IntegrityError, match="lease_only_while_running"):
        c.execute(text("UPDATE analysis_jobs SET state = 'RUNNING' WHERE id = :j"), {"j": job_id})
    with engine.begin() as c, pytest.raises(IntegrityError, match="finished_at_matches_state"):
        c.execute(text("UPDATE analysis_jobs SET state = 'COMPLETED' WHERE id = :j"), {"j": job_id})
    with engine.begin() as c:
        c.execute(text("UPDATE analysis_jobs SET state = 'RUNNING', lease_owner = 'w1', lease_expires_at = now() + interval '1 minute', attempt = 1 WHERE id = :j"), {"j": job_id})


def test_results_are_immutable_except_to_supersede_once(db):
    engine, case_id, job_id = db
    with engine.begin() as c:
        e1, e2 = execution(c, case_id, job_id), execution(c, case_id, job_id, fingerprint="e" * 64)
        ins = "INSERT INTO analysis_results (id, execution_id, job_id, case_id, module_id, schema_version, status, envelope) VALUES (gen_random_uuid(), :e, :j, :c, 'NEX-MET', '1.0', 'COMPLETED', '{}') RETURNING id"
        r1 = c.execute(text(ins), {"e": e1, "j": job_id, "c": case_id}).scalar_one()
        r2 = c.execute(text(ins), {"e": e2, "j": job_id, "c": case_id}).scalar_one()
    for stmt in ("UPDATE analysis_results SET envelope = '{\"x\": 1}' WHERE id = :r", "UPDATE analysis_results SET status = 'FAILED' WHERE id = :r", "DELETE FROM analysis_results WHERE id = :r"):
        with engine.begin() as c, pytest.raises(DBAPIError, match="cannot be changed|not permitted"):
            c.execute(text(stmt), {"r": r1})
    with engine.begin() as c:
        c.execute(text("UPDATE analysis_results SET superseded_at = now(), superseded_by = :n WHERE id = :r"), {"r": r1, "n": r2})
    with engine.begin() as c, pytest.raises(DBAPIError, match="superseded once"):
        c.execute(text("UPDATE analysis_results SET superseded_at = now(), superseded_by = :r WHERE id = :n"), {"r": r1, "n": r1})


def test_findings_artifacts_and_outbox_are_append_only_and_confidence_is_guarded(db):
    engine, case_id, job_id = db
    with engine.begin() as c:
        e = execution(c, case_id, job_id)
        r = c.execute(text("INSERT INTO analysis_results (id, execution_id, job_id, case_id, module_id, schema_version, status, envelope) VALUES (gen_random_uuid(), :e, :j, :c, 'NEX-MET', '1.0', 'COMPLETED', '{}') RETURNING id"), {"e": e, "j": job_id, "c": case_id}).scalar_one()
        f = c.execute(text("INSERT INTO analysis_findings (id, result_id, case_id, module_id, evidence_ids, assertion, finding_type, title, score, score_kind, payload) "
                           "VALUES (gen_random_uuid(), :r, :c, 'NEX-MET', ARRAY[gen_random_uuid()], 'OBSERVATION', 'ENCODER_TAG', 'Encoder tag', 0.1, 'METHOD_SPECIFIC', '{}') RETURNING id"), {"r": r, "c": case_id}).scalar_one()
        a = c.execute(text("INSERT INTO artifact_records (id, case_id, kind, storage_key, sha256, size_bytes, mime_type, execution_id, attributes) "
                           "VALUES (gen_random_uuid(), :c, 'REPORT_JSON', :k, :s, 10, 'application/json', :e, '{}') RETURNING id"), {"c": case_id, "k": f"Derived/{uuid.uuid4()}", "s": "1" * 64, "e": e}).scalar_one()
        o = c.execute(text("INSERT INTO outbox_events (id, event_type, aggregate_type, aggregate_id, case_id, payload) VALUES (gen_random_uuid(), 'analysis.module.completed', 'execution', :e, :c, '{}') RETURNING id"), {"e": e, "c": case_id}).scalar_one()
    for stmt, rid in (("UPDATE analysis_findings SET title = 'x' WHERE id = :i", f), ("DELETE FROM artifact_records WHERE id = :i", a), ("UPDATE outbox_events SET payload = '{}' WHERE id = :i", o)):
        with engine.begin() as c, pytest.raises(DBAPIError, match="not permitted"):
            c.execute(text(stmt), {"i": rid})
    with engine.begin() as c, pytest.raises(IntegrityError, match="confidence_only_when_calibrated"):
        c.execute(text("INSERT INTO analysis_findings (id, result_id, case_id, module_id, evidence_ids, assertion, finding_type, title, score, score_kind, confidence, payload) "
                       "VALUES (gen_random_uuid(), :r, :c, 'NEX-IMG', ARRAY[gen_random_uuid()], 'INFERENCE', 'X', 'x', 0.9, 'METHOD_SPECIFIC', 0.9, '{}')"), {"r": r, "c": case_id})
    with engine.begin() as c, pytest.raises(IntegrityError, match="event_type_format"):
        c.execute(text("INSERT INTO outbox_events (id, event_type, aggregate_type, aggregate_id, payload) VALUES (gen_random_uuid(), 'Bad Event', 'job', gen_random_uuid(), '{}')"))
