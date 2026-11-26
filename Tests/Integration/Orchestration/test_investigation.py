"""Step 7: evidence graph (NEX-EGC), reconstruction (NEX-REC), reviews (NEX-INV) and reports (NEX-RPT), end to end."""

import hashlib
import io
import json

import pytest
from PIL import Image
from sqlalchemy import create_engine, text

from Tests.Integration.Orchestration.test_sources_lineage import _page, drain, site  # noqa: F401 — fixture
from Tests.Integration.Orchestration.test_tmir import API, api, fresh, new_case, upload  # noqa: F401 — fixtures

pytestmark = pytest.mark.postgres


def _exif_jpeg(when: str) -> bytes:
    exif = Image.Exif()
    exif.get_ifd(0x8769)[0x9003] = when  # DateTimeOriginal
    buf = io.BytesIO()
    Image.linear_gradient("L").resize((96, 64)).convert("RGB").save(buf, "JPEG", exif=exif, quality=90)
    return buf.getvalue()


def test_graph_reconstruction_reviews_and_reports(api, fresh, media):
    case_id = new_case(api)
    assert api.get(f"{API}/cases/{case_id}/graph").json()["error"]["code"] == "GRAPH_NOT_BUILT"
    early = api.post(f"{API}/cases/{case_id}/reviews", json={"subject_type": "CASE_CONCLUSION", "subject_id": case_id,
                                                              "decision": "INCONCLUSIVE", "rationale": "too early"})
    assert early.status_code == 409 and early.json()["error"]["code"] == "RECONSTRUCTION_REQUIRED"
    evidence = upload(api, case_id, media["jpeg_exif"], "camera.jpg", "image/jpeg")
    drain(api)

    graph = api.get(f"{API}/cases/{case_id}/graph").json()["data"]
    types = {n["type"] for n in graph["nodes"]}
    assert {"CASE", "EVIDENCE"} <= types and graph["counts"]["nodes_evidence"] == 1
    assert all(e["record"] for e in graph["edges"])  # every edge names its supporting record
    assert {"from": case_id, "to": evidence["evidence_id"], "type": "CONTAINS"}.items() <= next(e for e in graph["edges"] if e["type"] == "CONTAINS").items()

    rec = api.get(f"{API}/cases/{case_id}/reconstruction").json()["data"]
    kinds = {(t["kind"], t["time"]) for t in rec["timeline"]}
    assert ("CLAIMED_CREATION", "2026-01-02T03:04:05+00:00") in kinds and any(k == "RECEIVED" for k, _ in kinds)
    assert rec["conflicts"] == []

    final = api.post(f"{API}/cases/{case_id}/reports", json={"kind": "FINAL"})
    assert final.status_code == 409 and final.json()["error"]["code"] == "CONCLUSION_REQUIRED"

    finding = api.get(f"{API}/evidence/{evidence['evidence_id']}/analysis").json()["data"]["findings"][0]
    first = api.post(f"{API}/cases/{case_id}/reviews", json={"subject_type": "FINDING", "subject_id": finding["finding_id"],
                                                              "decision": "ACCEPTED", "rationale": "Matches the camera's record"})
    assert first.status_code == 201 and first.json()["data"]["version"] == 1
    second = api.post(f"{API}/cases/{case_id}/reviews", json={"subject_type": "FINDING", "subject_id": finding["finding_id"],
                                                               "decision": "NEEDS_MORE_EVIDENCE", "rationale": "Ask for the original card"}).json()["data"]
    assert second["version"] == 2
    missing = api.post(f"{API}/cases/{case_id}/reviews", json={"subject_type": "RELATIONSHIP", "subject_id": evidence["evidence_id"],
                                                                "decision": "REJECTED", "rationale": "not a relationship"})
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "REVIEW_SUBJECT_NOT_FOUND"
    assert api.post(f"{API}/cases/{case_id}/reviews", json={"subject_type": "FINDING", "subject_id": finding["finding_id"],
                                                             "decision": "ACCEPTED", "rationale": ""}).status_code == 422
    conclusion = api.post(f"{API}/cases/{case_id}/reviews", json={"subject_type": "CASE_CONCLUSION", "subject_id": case_id,
                                                                   "decision": "INCONCLUSIVE", "rationale": "One file, no source"}).json()["data"]
    assert conclusion["reconstruction_result_id"] == rec["result_id"]
    current = api.get(f"{API}/cases/{case_id}/reviews?current=true").json()["data"]
    assert len(api.get(f"{API}/cases/{case_id}/reviews").json()["data"]) == 3 and len(current) == 2
    assert next(r for r in current if r["subject_type"] == "FINDING")["decision"] == "NEEDS_MORE_EVIDENCE"

    draft = api.post(f"{API}/cases/{case_id}/reports", json={"kind": "DRAFT"})
    assert draft.status_code == 202 and draft.json()["data"]["state"] == "QUEUED"
    report_id = draft.json()["data"]["report_id"]
    assert api.get(f"{API}/reports/{report_id}/download").json()["error"]["code"] == "REPORT_NOT_READY"
    final = api.post(f"{API}/cases/{case_id}/reports", json={"kind": "FINAL"}).json()["data"]
    assert (final["version"], final["kind"]) == (2, "FINAL")
    drain(api)

    report = api.get(f"{API}/reports/{report_id}").json()["data"]
    assert report["state"] == "GENERATED", report["error"]
    assert report["summary"]["conclusion"] == "INCONCLUSIVE" and report["summary"]["evidence"] == 1
    pdf = api.get(f"{API}/reports/{report_id}/download")
    assert pdf.content.startswith(b"%PDF") and pdf.headers["x-report-sha256"] == hashlib.sha256(pdf.content).hexdigest() == report["pdf_sha256"]
    doc = api.get(f"{API}/reports/{report_id}/download?format=json")
    assert hashlib.sha256(doc.content).hexdigest() == report["json_sha256"]
    body = json.loads(doc.content)
    assert body["evidence"][0]["sha256"] == evidence["sha256"] and body["conclusion"]["decision"] == "INCONCLUSIVE"
    assert any(m["module"] == "NEX-REC" for m in body["modules"]) and body["timeline"]
    assert api.get(f"{API}/reports/{final['report_id']}").json()["data"]["state"] == "GENERATED"
    assert [r["version"] for r in api.get(f"{API}/cases/{case_id}/reports").json()["data"]] == [2, 1]

    engine = create_engine(fresh[0])
    with engine.connect() as conn:  # reviews and graph snapshots are append-only; reports are never deleted
        for sql in ("UPDATE reviews SET decision = 'ACCEPTED'", "DELETE FROM graph_snapshots", "DELETE FROM reports"):
            with pytest.raises(Exception, match="append-only|cannot be deleted|not allowed"):
                conn.execute(text(sql))
            conn.rollback()
    engine.dispose()


def test_time_conflict_between_file_and_source(api, site):
    base, routes = site
    routes["/post.html"] = (200, "text/html", _page("/img/a.jpg", "2025-06-01T00:00:00Z", "Post"))
    routes["/img/a.jpg"] = (200, "image/jpeg", _exif_jpeg("2026:01:02 03:04:05"))
    case_id = new_case(api)
    api.post(f"{API}/cases/{case_id}/sources", json={"url": base + "/post.html"})
    drain(api)
    rec = api.get(f"{API}/cases/{case_id}/reconstruction").json()["data"]
    assert {t["kind"] for t in rec["timeline"]} >= {"CLAIMED_CREATION", "CLAIMED_PUBLICATION", "RECEIVED", "RETRIEVED"}
    assert len(rec["conflicts"]) == 1 and "claims creation after SRC-" in rec["conflicts"][0]["title"]
    graph = api.get(f"{API}/cases/{case_id}/graph").json()["data"]
    assert graph["counts"]["edges_retrieved_as"] == 1
