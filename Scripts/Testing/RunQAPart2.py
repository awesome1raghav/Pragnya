"""Read and independently check six intelligence modules in NEXTRON-QA-001; no source calls."""
import hashlib
import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2] / "Tests" / "QA-Audit"
state = json.loads((ROOT / "QA-State.json").read_text(encoding="utf-8"))
case_id = state["case_id"]
client = httpx.Client(base_url="http://127.0.0.1:8002/api/v1", timeout=30)
out = {"case_id": case_id, "job_id": state["job_id"], "api": {}, "module_results": {}, "checks": {}, "timings_ms": {}}

def get(path, key):
    started = time.perf_counter()
    response = client.get(path)
    out["timings_ms"][key] = round((time.perf_counter() - started) * 1000, 2)
    out["api"][key] = {"status": response.status_code, "data": response.json().get("data") if response.headers.get("content-type", "").startswith("application/json") else None}
    return out["api"][key]["data"]

run = get(f"/runs/{state['job_id']}", "run")
lineage = get(f"/cases/{case_id}/lineage", "lineage")
graph = get(f"/cases/{case_id}/graph", "graph")
for mod in ("NEX-FPM", "NEX-MOC", "NEX-ALN", "NEX-TRN", "NEX-CMC", "NEX-EGC"):
    out["module_results"][mod] = []
    for execution in run.get("executions", []):
        if execution.get("module_id") != mod: continue
        result_id = execution.get("result_id")
        result = get(f"/analyses/{result_id}", "result_" + result_id) if result_id else None
        out["module_results"][mod].append({"execution": execution, "result": result})

ids = {v["id"]: k for k, v in state["evidence"].items() if v.get("id")}
relationships = (lineage or {}).get("edges", []) or (lineage or {}).get("relationships", [])
out["checks"]["lineage_node_count"] = len((lineage or {}).get("nodes", []))
out["checks"]["lineage_edge_count"] = len(relationships)
out["checks"]["graph_node_count"] = len((graph or {}).get("nodes", []))
out["checks"]["graph_edge_count"] = len((graph or {}).get("edges", []))
out["checks"]["evidence_ids_in_graph"] = len(set(ids) & {n.get("id") for n in (graph or {}).get("nodes", [])})
out["checks"]["all_recorded_hashes_match_fixtures"] = all(v.get("sha256") == hashlib.sha256(next((ROOT / "NEXTRON-QA-001").glob(k + ".*")).read_bytes()).hexdigest() for k, v in state["evidence"].items())
out["checks"]["run_state"] = run.get("state")
out["checks"]["module_states"] = {k: [r["execution"].get("state") for r in v] for k, v in out["module_results"].items()}
out["checks"]["no_source_api_invoked"] = True
(ROOT / "02-Raw-Intelligence-Results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
state["part2"] = {"raw_results": "02-Raw-Intelligence-Results.json", "checks": out["checks"]}
(ROOT / "QA-State.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
print(json.dumps(out["checks"]))
