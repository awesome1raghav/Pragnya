"""Database-backed NEX-BTK budget, restart, scope, review, and report traceability."""
import hashlib
import shutil
import uuid

import pytest
from sqlalchemy import select, text

from Backend.App.Modules.NexRpt.Service import gather, render_pdf
from Backend.App.Storage.StorageInterface import original_key
from Backend.App.Workers import JobService
from Database.PostgreSQL.Models import (AnalysisJob, BacktrackingComparison, Case, Evidence, Report, SourceObservation, SourceRecord)
from Tests.conftest import make_worker

pytestmark = pytest.mark.postgres
CORPUS = __import__("pathlib").Path(__file__).resolve().parents[2] / "QA-Audit" / "NEXTRON-QA-001"


def _case_and_media(client):
    storage = client.app.state.storage
    with client.app.state.session_factory() as session:
        case = Case(title="[Test] BTK local workflow", created_by="test")
        other_case = Case(title="[Test] BTK other case", created_by="test")
        session.add_all((case, other_case))
        session.flush()
        ids = []
        for filename in ("VID-01.mp4", "VID-02.mp4", "VID-04.mp4"):
            source = CORPUS / filename
            data = source.read_bytes()
            evidence_id = uuid.uuid4()
            key = original_key(case.id, evidence_id)
            staged = storage.new_staging_path()
            shutil.copyfile(source, staged)
            storage.promote_original(staged, key)
            session.add(Evidence(id=evidence_id, case_id=case.id, original_filename=filename,
                                 media_type="VIDEO", detected_format="MP4", mime_type="video/mp4", size_bytes=len(data),
                                 sha256=hashlib.sha256(data).hexdigest(), storage_key=key,
                                 source_type="SOURCE_RETRIEVAL" if filename == "VID-02.mp4" else "USER_UPLOAD",
                                 acquisition_method="CONNECTOR_RETRIEVAL" if filename == "VID-02.mp4" else "DIRECT_UPLOAD",
                                 acquired_by="test", received_at=case.created_at))
            ids.append(evidence_id)
        source = SourceRecord(case_id=case.id, url="https://example.org/blocked", normalized_url="https://example.org/blocked",
                              platform="GENERIC", state="RESTRICTED", revision=1, created_by="test")
        session.add(source)
        session.flush()
        session.add(SourceObservation(source_id=source.id, revision=1, connector="generic", outcome="RESTRICTED",
                                      requested_url=source.url, redirects=[], metadata_={}))
        retrieved = SourceRecord(case_id=case.id, url="https://example.org/video", normalized_url="https://example.org/video",
                                 platform="GENERIC", state="RETRIEVED", revision=1, created_by="test", evidence_id=ids[1])
        session.add(retrieved)
        session.flush()
        session.add(SourceObservation(source_id=retrieved.id, revision=1, connector="generic", outcome="RETRIEVED",
                                      requested_url=retrieved.url, evidence_id=ids[1], redirects=[], metadata_={}))
        session.commit()
        return case.id, other_case.id, ids


def test_local_expansion_review_report_and_case_scope(client):
    case_id, other_case, ids = _case_and_media(client)
    root = f"/api/v1/cases/{case_id}/backtracking"
    bad = client.post(f"/api/v1/cases/{other_case}/backtracking/verify",
                      json={"seed_evidence_id": str(ids[0]), "candidate_evidence_id": str(ids[1])})
    assert bad.status_code == 404
    with client.app.state.session_factory() as session:
        forged_id = uuid.uuid4()
        valid_id = uuid.uuid4()
        key = original_key(other_case, forged_id)
        staged = client.app.state.storage.new_staging_path()
        shutil.copyfile(CORPUS / "VID-01.mp4", staged)
        client.app.state.storage.promote_original(staged, key)
        session.add(Evidence(id=forged_id, case_id=other_case, original_filename="forged.mp4", media_type="VIDEO",
                             detected_format="MP4", mime_type="video/mp4", size_bytes=(CORPUS / "VID-01.mp4").stat().st_size,
                             sha256="0" * 64, storage_key=key, source_type="USER_UPLOAD",
                             acquisition_method="DIRECT_UPLOAD", acquired_by="test",
                             received_at=session.get(Case, other_case).created_at))
        valid_key = original_key(other_case, valid_id)
        staged = client.app.state.storage.new_staging_path()
        shutil.copyfile(CORPUS / "VID-02.mp4", staged)
        client.app.state.storage.promote_original(staged, valid_key)
        session.add(Evidence(id=valid_id, case_id=other_case, original_filename="valid.mp4", media_type="VIDEO",
                             detected_format="MP4", mime_type="video/mp4", size_bytes=(CORPUS / "VID-02.mp4").stat().st_size,
                             sha256=hashlib.sha256((CORPUS / "VID-02.mp4").read_bytes()).hexdigest(), storage_key=valid_key,
                             source_type="USER_UPLOAD", acquisition_method="DIRECT_UPLOAD", acquired_by="test",
                             received_at=session.get(Case, other_case).created_at))
        session.commit()
    assert client.post(f"/api/v1/cases/{other_case}/backtracking/verify", json={
        "seed_evidence_id": str(forged_id), "candidate_evidence_id": str(valid_id)}).status_code == 409
    occurrences = client.get(f"{root}/source-occurrences").json()["data"]["source_occurrences"]
    assert any(x["backtracking_access"] == "METADATA_ONLY" and x["preserved_evidence_id"] is None for x in occurrences)
    assert any(x["backtracking_access"] == "LOCAL_VIDEO" and x["preserved_evidence_id"] == str(ids[1]) for x in occurrences)
    assert client.post(f"{root}/expand", json={"seed_evidence_id": str(ids[0]), "max_comparisons": 101}).status_code == 422
    queued = client.post(f"{root}/expand", json={"seed_evidence_id": str(ids[0]), "max_comparisons": 3})
    assert queued.status_code == 202
    job_id = queued.json()["data"]["job_id"]
    assert client.post(f"{root}/expand", json={"seed_evidence_id": str(ids[0]), "max_comparisons": 3}).json()["data"]["job_id"] == job_id
    worker = make_worker(client.app)
    assert worker.process_one() == uuid.UUID(job_id)
    with client.app.state.session_factory() as session:
        records = session.scalars(select(BacktrackingComparison).where(BacktrackingComparison.case_id == case_id)).all()
        assert len(records) == 3
        assert len({frozenset((r.seed_evidence_id, r.candidate_evidence_id)) for r in records}) == 3
    overview = client.get(f"{root}/overview").json()["data"]
    assert overview["coverage"] == {"compared_pairs": 3, "possible_video_pairs": 3, "pair_percent": 100.0}
    candidate = next(r for r in records if r.status == "CANDIDATE_MATCH")
    reviewed = client.post(f"/api/v1/cases/{case_id}/reviews", json={"subject_type": "BACKTRACK_COMPARISON",
        "subject_id": str(candidate.id), "decision": "INCONCLUSIVE", "rationale": "Shared frames do not prove origin."})
    assert reviewed.status_code == 201
    inspected = client.get(f"{root}/comparisons/{candidate.id}").json()["data"]
    assert inspected["review"]["decision"] == "INCONCLUSIVE"
    with client.app.state.session_factory() as session:
        report = Report(case_id=case_id, version=1, kind="DRAFT", state="QUEUED", requested_by="test", summary={})
        session.add(report)
        session.flush()
        doc = gather(session, report)
        assert {r["comparison_id"] for r in doc["backtracking"]} == {str(r.id) for r in records}
        assert next(r for r in doc["backtracking"] if r["comparison_id"] == str(candidate.id))["review"]["decision"] == "INCONCLUSIVE"
        assert {o["outcome"] for o in doc["source_occurrences"]} == {"RESTRICTED", "RETRIEVED"}
        assert render_pdf(doc).startswith(b"%PDF")
        session.rollback()


def test_expired_lease_resumes_without_duplicate_records(client):
    case_id, _, ids = _case_and_media(client)
    root = f"/api/v1/cases/{case_id}/backtracking"
    first = client.post(f"{root}/compare", json={"seed_evidence_id": str(ids[0]), "candidate_evidence_id": str(ids[1])})
    assert first.status_code == 200 and first.json()["data"]["status"] == "CANDIDATE_MATCH"
    job_id = uuid.UUID(client.post(f"{root}/expand", json={"seed_evidence_id": str(ids[0]), "max_comparisons": 2}).json()["data"]["job_id"])
    settings = client.app.state.settings.model_copy(update={"JOB_RETRY_BASE_SECONDS": 0})
    with client.app.state.session_factory() as session:
        assert JobService.claim(session, "crashed-worker", lease_seconds=5).id == job_id
        job = session.get(AnalysisJob, job_id)
        job.progress = {"frontier": [[str(ids[0]), str(ids[2])]],
                        "seen": [":".join(sorted((str(ids[0]), str(ids[1]))))], "completed": 1, "matches": 1}
        session.flush()
        session.execute(text("UPDATE analysis_jobs SET lease_expires_at = now() - interval '1 second' WHERE id = :id"), {"id": job_id})
        session.commit()
    worker = make_worker(client.app)
    worker.settings = settings
    assert worker.process_one() == job_id
    with client.app.state.session_factory() as session:
        records = session.scalars(select(BacktrackingComparison).where(BacktrackingComparison.case_id == case_id)).all()
        assert len(records) == 2
        assert len({(r.seed_evidence_id, r.candidate_evidence_id, r.algorithm) for r in records}) == 2
