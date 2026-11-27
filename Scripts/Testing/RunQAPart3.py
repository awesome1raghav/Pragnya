"""Live Part 3 review/report audit in existing isolated NEXTRON-QA-001 only."""
import hashlib
import io
import json
import time
from pathlib import Path

import httpx

from Backend.App.Config import get_settings
from Backend.App.Storage.LocalStorage import LocalStorage
from Backend.App.Workers.Worker import Worker
from Database.PostgreSQL.Connection import EngineOptions, create_database_engine
from Database.PostgreSQL.Session import create_session_factory
from Database.PostgreSQL.Models import AnalysisJob
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2] / "Tests" / "QA-Audit"
state = json.loads((ROOT / "QA-State.json").read_text(encoding="utf-8"))
cid = state["case_id"]
client = httpx.Client(base_url="http://127.0.0.1:8002/api/v1", timeout=30)
out = {"case_id": cid, "requests": {}, "reviews": [], "reports": [], "checks": {}}

def call(method, path, **kw):
    start = time.perf_counter()
    r = client.request(method, path, **kw)
    return {"status": r.status_code, "elapsed_ms": round((time.perf_counter()-start)*1000,2), "body": r.json()}

out["requests"]["reconstruction"] = call("GET", f"/cases/{cid}/reconstruction")
rec = out["requests"]["reconstruction"]["body"].get("data") or {}
out["checks"]["timeline_ordered"] = [x["time"] for x in rec.get("timeline",[])] == sorted(x["time"] for x in rec.get("timeline",[]))
out["checks"]["timeline_count"] = len(rec.get("timeline",[]))
out["checks"]["timeline_measured_labels"] = all(x.get("by") == "NEXTRON (measured)" for x in rec.get("timeline",[]) if x.get("kind") == "RECEIVED")

raw2 = json.loads((ROOT / "02-Raw-Intelligence-Results.json").read_text(encoding="utf-8"))
finding = raw2["module_results"]["NEX-MOC"][0]["result"]["envelope"]["findings"][0]
fid = finding["finding_id"]
out["checks"]["finding_before"] = finding
prior = call("GET", f"/cases/{cid}/reviews")["body"].get("data") or []
if not prior:
    for decision in ("ACCEPTED", "REJECTED", "INCONCLUSIVE", "NEEDS_MORE_EVIDENCE"):
        out["reviews"].append(call("POST", f"/cases/{cid}/reviews", json={"subject_type":"FINDING","subject_id":fid,"decision":decision,"rationale":f"Controlled QA audit: {decision} revision; not a forensic conclusion"}))
    out["reviews"].append(call("POST", f"/cases/{cid}/reviews", json={"subject_type":"CASE_CONCLUSION","subject_id":cid,"decision":"INCONCLUSIVE","rationale":"Controlled fixtures show candidate links and unresolved audio discrepancy; no verified source or calibrated accuracy"}))
else:
    out["reviews"] = [{"status":200,"body":{"data":r},"elapsed_ms":None} for r in sorted(prior, key=lambda x:(x["subject_type"]=="CASE_CONCLUSION",x["version"]))]
out["requests"]["reviews"] = call("GET", f"/cases/{cid}/reviews")
out["requests"]["reviews_current"] = call("GET", f"/cases/{cid}/reviews?current=true")
existing = call("GET", f"/cases/{cid}/reports")["body"].get("data") or []
for kind in ("DRAFT","FINAL"):
    row = next((r for r in existing if r["kind"] == kind), None)
    out["requests"][kind.lower()] = {"status":200,"body":{"data":row},"elapsed_ms":None} if row else call("POST", f"/cases/{cid}/reports", json={"kind":kind})

settings = get_settings()
engine = create_database_engine(settings.DATABASE_URL, EngineOptions(pool_size=1, max_overflow=0, pool_timeout_seconds=5, connect_timeout_seconds=3))
factory = create_session_factory(engine)
worker = Worker(settings, factory, LocalStorage(settings.STORAGE_ROOT), worker_id="qa-part3-report-only")
worker.register()
try:
    for expected in (out["requests"]["draft"], out["requests"]["final"]):
        if expected["status"] not in (200,202): continue
        with factory() as session:
            queued = session.scalars(select(AnalysisJob).where(AnalysisJob.state == "QUEUED")).all()
            if not queued or any(j.job_type != "REPORT_GENERATION" or j.case_id != __import__("uuid").UUID(cid) for j in queued):
                raise RuntimeError("Unsafe queue: non-report job present; worker not started")
        out["checks"].setdefault("worker_claimed", []).append(str(worker.process_one()))
finally:
    worker.deregister()
    engine.dispose()

out["requests"]["report_list"] = call("GET", f"/cases/{cid}/reports")
for report in (out["requests"]["report_list"]["body"].get("data") or []):
    report_id = report["report_id"]
    item = {"record":report}
    for fmt in ("json", "pdf"):
        response = client.get(f"/reports/{report_id}/download", params={"format":fmt})
        blob = response.content
        item[fmt] = {"status":response.status_code,"bytes":len(blob),"sha256":hashlib.sha256(blob).hexdigest(),"header_sha256":response.headers.get("x-report-sha256")}
        if response.status_code == 200:
            (ROOT / f"03-Report-{report['kind']}-v{report['version']}.{fmt}").write_bytes(blob)
            if fmt == "json":
                document = json.loads(blob)
                item[fmt]["content"] = {"keys":list(document),"evidence_count":len(document.get("evidence",[])),"module_count":len(document.get("modules",[])),"review_count":len(document.get("reviews",[])),"case":document.get("case"),"statement":document.get("statement")}
            else:
                item[fmt]["pdf_signature"] = blob[:5].decode("ascii",errors="replace")
    out["reports"].append(item)
out["checks"]["review_versions"] = [r["body"].get("data",{}).get("version") for r in out["reviews"][:4]]
out["checks"]["report_hashes_match"] = all(v[fmt]["sha256"] == v[fmt]["header_sha256"] for v in out["reports"] for fmt in ("json","pdf") if v[fmt]["status"] == 200)
(ROOT / "03-Raw-Review-Report-Results.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
state["part3"] = {"raw_results":"03-Raw-Review-Report-Results.json","checks":out["checks"] | {"finding_before":"saved in raw results"}}
(ROOT / "QA-State.json").write_text(json.dumps(state,indent=2),encoding="utf-8")
print(json.dumps({"timeline":out["checks"]["timeline_count"],"reviews":len(out["reviews"]),"versions":out["checks"]["review_versions"],"reports":[(r["record"]["kind"],r["record"]["state"],r["json"]["status"],r["pdf"]["status"]) for r in out["reports"]],"hashes_match":out["checks"]["report_hashes_match"]}))
