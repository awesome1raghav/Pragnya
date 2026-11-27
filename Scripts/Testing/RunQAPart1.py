"""One live controlled audit case for each of NEX-CM/CAP/EVD/MET/IMG/VID/AUD/PRV."""
import hashlib
import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2] / "Tests" / "QA-Audit"
FIX = ROOT / "NEXTRON-QA-001"
BASE = "http://127.0.0.1:8002/api/v1"
ROOT.mkdir(exist_ok=True)
state_path = ROOT / "QA-State.json"
state = json.loads(state_path.read_text()) if state_path.exists() else {"dataset": "NEXTRON-QA-001", "evidence": {}, "observations": {}, "fixture_root": str(FIX)}
client = httpx.Client(base_url=BASE, timeout=120)

def call(method, path, **kw):
    started = time.perf_counter()
    try:
        r = client.request(method, path, **kw)
        payload = r.json() if "json" in r.headers.get("content-type", "") else None
        return {"status": r.status_code, "elapsed_ms": round((time.perf_counter()-started)*1000), "body": payload, "bytes": len(r.content)}
    except Exception as e:
        return {"status": 0, "error": type(e).__name__ + ": " + str(e)[:250]}

def save():
    state_path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")

if not state.get("case_id"):
    created = call("POST", "/cases", json={"title": "NEXTRON-QA-001 controlled audit", "description": "Self-generated media, isolated E2E database", "priority": "HIGH", "tags": ["QA", "controlled"], "notes": "Part 1 validation"})
    state["observations"]["case_create"] = created
    state["case_id"] = (created.get("body") or {}).get("data", {}).get("case_id")
    save()
cid = state.get("case_id")
if not cid:
    raise SystemExit("Case creation failed; see QA-State.json")

for fid in ["IMG-01", "IMG-02", "IMG-03", "IMG-04", "VID-01", "VID-02", "VID-03", "VID-04", "VID-05", "AUD-01", "AUD-02", "AUD-03", "AUD-04"]:
    if fid in state["evidence"]: continue
    path = next(FIX.glob(fid + ".*"))
    with path.open("rb") as stream:
        result = call("POST", f"/cases/{cid}/evidence", files={"file": (path.name, stream, "image/jpeg" if fid.startswith("IMG") else "video/mp4" if fid.startswith("VID") else "audio/wav")})
    data = (result.get("body") or {}).get("data") or {}
    state["evidence"][fid] = {"id": data.get("evidence_id"), "status": result["status"], "sha256": data.get("sha256"), "local_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "elapsed_ms": result.get("elapsed_ms"), "response": result.get("body") if result["status"] != 201 else None}
    save()

for fid in ["NEG-01", "NEG-02"]:
    path = FIX / (fid + ".jpg")
    with path.open("rb") as stream:
        state["observations"][fid] = call("POST", f"/cases/{cid}/evidence", files={"file": (path.name, stream, "image/jpeg")})

for fid, entry in state["evidence"].items():
    eid = entry.get("id")
    if not eid: continue
    entry["metadata"] = call("GET", f"/evidence/{eid}/metadata")
    entry["integrity"] = call("POST", f"/evidence/{eid}/verify-integrity")
    entry["history"] = call("GET", f"/evidence/{eid}/history")
    download = client.get(f"/evidence/{eid}/download")
    entry["download"] = {"status": download.status_code, "sha256": hashlib.sha256(download.content).hexdigest(), "bytes": len(download.content)}
    entry["analysis"] = call("GET", f"/evidence/{eid}/analysis")
    save()

state["observations"]["case_update"] = call("PATCH", f"/cases/{cid}", json={"notes": "Part 1 executed", "title": "NEXTRON-QA-001 controlled audit"})
for name, path in {"case": f"/cases/{cid}", "list": "/cases?search=NEXTRON-QA-001&page=1&page_size=1", "statistics": "/cases/statistics", "summary": f"/cases/{cid}/summary", "events": f"/cases/{cid}/events", "invalid_case": "/cases/00000000-0000-0000-0000-000000000000"}.items():
    state["observations"][name] = call("GET", path)
state["observations"]["archive"] = call("POST", f"/cases/{cid}/archive", json={})
state["observations"]["reopen"] = call("POST", f"/cases/{cid}/reopen")
state["observations"]["run"] = call("POST", f"/cases/{cid}/runs", json={})
job_id = ((state["observations"]["run"].get("body") or {}).get("data") or {}).get("job_id")
state["job_id"] = job_id
save()
if job_id:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        detail = call("GET", f"/runs/{job_id}")
        state["observations"]["run_detail"] = detail
        save()
        job_status = ((detail.get("body") or {}).get("data") or {}).get("job", {}).get("status")
        if job_status in {"COMPLETED", "PARTIALLY_COMPLETED", "FAILED", "CANCELLED"}: break
        time.sleep(3)
print(json.dumps({"case_id": cid, "uploaded": sum(bool(e.get("id")) for e in state["evidence"].values()), "job_id": job_id, "run_status": job_status if job_id else None}))
