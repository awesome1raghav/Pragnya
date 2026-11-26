"""Outage drill against the running local stack (Step 9): stop a dependency, check what NEXTRON says and does, restart it,
check that it recovers. Prints a JSON report of what was measured.

  PostgreSQL down: /health/ready answers 503 naming the database; a write answers 503 (no partial record); the worker
                   process stays alive; after the restart the API is ready again, the worker heartbeats again, and a new
                   run completes.
  Neo4j down:      evidence intake and analysis still complete; /system/projections reports Neo4j unreachable and lag;
                   after the restart the lag returns to 0.

Usage (repository root, API on NEXTRON_API, worker running, Compose containers nextron-postgres and nextron-neo4j):
  .\\.venv\\Scripts\\python.exe -m Scripts.Testing.OutageDrill
This stops and restarts those containers; nothing is deleted.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import time

import httpx
from PIL import Image

API = os.environ.get("NEXTRON_API", "http://127.0.0.1:8001/api/v1")
DOCKER = shutil.which("docker") or r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"


def docker(*args: str) -> None:
    subprocess.run([DOCKER, *args], check=True, capture_output=True)


def wait(predicate, timeout: float, step: float = 0.5):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            value = predicate()
            if value:
                return round(time.monotonic() - start, 1), value
        except httpx.HTTPError:
            pass
        time.sleep(step)
    raise TimeoutError(f"condition not met within {timeout} s")


def png(seed: int) -> bytes:
    buf = io.BytesIO()
    Image.effect_noise((64, 48), 40 + seed).convert("RGB").save(buf, "PNG")
    return buf.getvalue()


def run_finishes(c: httpx.Client, case_id: str, seed: int, timeout: float = 120) -> dict:
    up = c.post(f"{API}/cases/{case_id}/evidence", files={"file": (f"drill-{seed}.png", png(seed), "image/png")}).json()["data"]
    job = up["analysis_job"]["job_id"]
    secs, state = wait(lambda: (s := c.get(f"{API}/jobs/{job}").json()["data"]["state"]) not in ("QUEUED", "RUNNING") and s, timeout)
    return {"job": up["analysis_job"]["job_number"], "state": state, "seconds": secs}


def main() -> int:
    report: dict = {}
    with httpx.Client(timeout=10) as c:
        case_id = c.post(f"{API}/cases", json={"title": "[Drill] Outage drill"}).json()["data"]["case_id"]
        report["baseline_run"] = run_finishes(c, case_id, 1)

        # ── PostgreSQL ──
        docker("stop", "nextron-postgres")
        try:
            secs, r = wait(lambda: (r := c.get(f"{API}/health/ready")).status_code == 503 and r, 30)
            body = r.json()
            write = c.post(f"{API}/cases", json={"title": "[Drill] during outage"})
            time.sleep(5)
            workers_alive = subprocess.run(["powershell", "-NoProfile", "-Command",
                                            "(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'Backend\\.App\\.Workers\\.Worker' }).Count"],
                                           capture_output=True, text=True).stdout.strip()
            report["postgres_down"] = {"ready_503_after_s": secs, "error_code": body["error"]["code"],
                                       "write_status": write.status_code, "write_code": write.json()["error"]["code"],
                                       "worker_processes_alive": int(workers_alive or 0)}
        finally:
            docker("start", "nextron-postgres")
        secs, _ = wait(lambda: c.get(f"{API}/health/ready").status_code == 200, 90)
        hb, _ = wait(lambda: c.get(f"{API}/system/workers").json()["data"]["alive"] >= 1, 90)
        titles = [x["title"] for x in c.get(f"{API}/cases", params={"search": "during outage"}).json()["data"]]
        report["postgres_recovered"] = {"ready_after_s": secs, "worker_alive_after_s": hb,
                                        "write_during_outage_stored": "[Drill] during outage" in titles,
                                        "run_after_recovery": run_finishes(c, case_id, 2)}

        # ── Neo4j ──
        docker("stop", "nextron-neo4j")
        try:
            run = run_finishes(c, case_id, 3)
            p = c.get(f"{API}/system/projections").json()["data"][0]
            report["neo4j_down"] = {"run": run, "reachable": p["reachable"], "lag_events": p["lag_events"], "error": (p["error"] or "")[:80]}
        finally:
            docker("start", "nextron-neo4j")
        secs, p = wait(lambda: (p := c.get(f"{API}/system/projections").json()["data"][0])["reachable"] and p["lag_events"] == 0 and p, 180, 2)
        report["neo4j_recovered"] = {"lag_zero_after_s": secs, "nodes": p["nodes"]}
    print(json.dumps(report, indent=2))
    ok = (report["postgres_down"]["error_code"] in ("SERVICE_NOT_READY", "DATABASE_UNAVAILABLE") and report["postgres_down"]["write_status"] == 503
          and report["postgres_down"]["worker_processes_alive"] >= 1 and not report["postgres_recovered"]["write_during_outage_stored"]
          and report["postgres_recovered"]["run_after_recovery"]["state"] in ("COMPLETED", "PARTIALLY_COMPLETED")
          and report["neo4j_down"]["run"]["state"] in ("COMPLETED", "PARTIALLY_COMPLETED") and report["neo4j_down"]["reachable"] is False)
    print("DRILL", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
