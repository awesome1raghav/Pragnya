"""Module contracts: what a valid finding and result look like, and what they refuse."""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from Backend.App.Contracts.Artifacts import ArtifactKind, ArtifactRef, InputKind, InputReference
from Backend.App.Contracts.ExecutionStates import ExecutionState, ScopeKind
from Backend.App.Contracts.Findings import Assertion, Finding, ScoreKind
from Backend.App.Contracts.ModuleResult import ModuleResult, input_fingerprint

EV = uuid.uuid4()
SHA = "a" * 64


def finding(**over):
    base = dict(module_id="NEX-IMG", evidence_ids=[EV], assertion=Assertion.OBSERVATION, finding_type="COMPRESSION_INCONSISTENCY",
                title="Two JPEG quantisation tables", score=0.42, score_kind=ScoreKind.METHOD_SPECIFIC,
                region={"x": 10, "y": 10, "w": 20, "h": 15}, limitations=["Re-encoding can produce the same pattern"])
    return Finding(**(base | over))


def result(**over):
    now = datetime.now(timezone.utc)
    base = dict(module_id="NEX-IMG", module_version="nex-img/0.1", case_id=uuid.uuid4(), evidence_ids=[EV], scope_kind=ScopeKind.EVIDENCE,
                job_id=uuid.uuid4(), execution_id=uuid.uuid4(), status=ExecutionState.COMPLETED,
                input_references=[InputReference(kind=InputKind.EVIDENCE, id=EV, sha256=SHA)],
                findings=[finding()], tool_versions={"pillow": "13.0.0"}, started_at=now, completed_at=now + timedelta(seconds=2), execution_time_ms=2000)
    return ModuleResult(**(base | over))


def test_valid_result_round_trips_through_json():
    r = result()
    again = ModuleResult.model_validate_json(r.model_dump_json())
    assert again == r
    schema = ModuleResult.model_json_schema()
    assert {"module_id", "case_id", "job_id", "execution_id", "status", "scope_kind", "module_version"} <= set(schema["required"])
    assert json.loads(r.model_dump_json())["schema_version"] == "1.0"


@pytest.mark.parametrize("over, message", [
    ({"score": 0.4, "score_kind": None}, "score and score_kind"),
    ({"score": None, "score_kind": ScoreKind.SIMILARITY}, "score and score_kind"),
    ({"confidence": 0.9}, "CALIBRATED_PROBABILITY"),
    ({"confidence": 0.9, "score_kind": ScoreKind.CALIBRATED_PROBABILITY}, "confidence_basis"),
    ({"confidence_basis": "Platt scaling on a held-out set"}, "confidence_basis without"),
    ({"region": {"x": 90, "y": 0, "w": 20, "h": 10}}, "inside the image"),
    ({"time_range": {"start_seconds": 5, "end_seconds": 2}}, "end_seconds"),
    ({"evidence_ids": []}, "at least 1"),
    ({"finding_type": "temporal break"}, "pattern"),
    ({"module_id": "IMG"}, "pattern"),
])
def test_findings_refuse_dishonest_or_malformed_values(over, message):
    with pytest.raises(ValidationError, match=message):
        finding(**over)


def test_calibrated_confidence_is_allowed_with_its_basis():
    f = finding(score=0.83, score_kind=ScoreKind.CALIBRATED_PROBABILITY, confidence=0.83, confidence_basis="Temperature scaling on FaceForensics++ c23 validation split")
    assert f.confidence == 0.83


@pytest.mark.parametrize("over, message", [
    ({"status": ExecutionState.RUNNING}, "terminal"),
    ({"status": ExecutionState.SKIPPED, "findings": []}, "status_reason"),
    ({"status": ExecutionState.UNAVAILABLE, "status_reason": "TOOL_UNAVAILABLE"}, "only COMPLETED or PARTIALLY_COMPLETED"),
    ({"status": ExecutionState.FAILED, "status_reason": "ERROR", "findings": []}, "at least one error"),
    ({"findings": [None]}, "Finding"),
    ({"confidence": 0.5}, "basis"),
])
def test_results_refuse_inconsistent_states(over, message):
    if over.get("findings") == [None]:
        over = {"findings": [finding(module_id="NEX-VID")]}
        message = "this result's module"
    with pytest.raises(ValidationError, match=message):
        result(**over)


def test_skipped_and_unavailable_results_are_valid_with_a_reason():
    assert result(status=ExecutionState.SKIPPED, status_reason="NOT_APPLICABLE", findings=[]).findings == []
    assert result(status=ExecutionState.UNAVAILABLE, status_reason="TOOL_UNAVAILABLE", findings=[], limitations=["No approved detector installed"]).status is ExecutionState.UNAVAILABLE


def test_findings_may_only_cite_covered_evidence():
    with pytest.raises(ValidationError, match="evidence this result covers"):
        result(findings=[finding(evidence_ids=[uuid.uuid4()])])


def test_input_references_are_pinned():
    with pytest.raises(ValidationError, match="pinned by sha256"):
        InputReference(kind=InputKind.EVIDENCE, id=EV)
    with pytest.raises(ValidationError, match="name the module"):
        InputReference(kind=InputKind.MODULE_RESULT, id=uuid.uuid4())
    with pytest.raises(ValidationError, match="revision"):
        InputReference(kind=InputKind.SOURCE_RECORD, id=uuid.uuid4())
    assert ArtifactRef(artifact_id=uuid.uuid4(), kind=ArtifactKind.FRAME, sha256=SHA, size_bytes=10, mime_type="image/png").kind is ArtifactKind.FRAME


def test_input_fingerprint_identifies_exact_inputs():
    a = InputReference(kind=InputKind.EVIDENCE, id=EV, sha256=SHA)
    b = InputReference(kind=InputKind.MODULE_RESULT, id=uuid.uuid4(), module_id="NEX-MET")
    fp = input_fingerprint("NEX-FPM", "1", {"hash": "phash"}, [a, b])
    assert len(fp) == 64 and fp == input_fingerprint("NEX-FPM", "1", {"hash": "phash"}, [b, a])  # order does not matter
    assert fp != input_fingerprint("NEX-FPM", "2", {"hash": "phash"}, [a, b])  # module version matters
    assert fp != input_fingerprint("NEX-FPM", "1", {"hash": "dhash"}, [a, b])  # parameters matter
    changed = InputReference(kind=InputKind.EVIDENCE, id=EV, sha256="b" * 64)
    assert fp != input_fingerprint("NEX-FPM", "1", {"hash": "phash"}, [changed, b])  # bytes matter
