"""Measured API performance on the running local stack (Step 9). Writes Benchmarks/Results/performance.json.

  read latency    p50 / p95 / max of common reads with 1 and 16 concurrent clients, over the data already stored
  upload          throughput of one streamed upload (validated, hashed, preserved), 25 and 200 MB
  analysis        wall time of an image run (all planned modules) as measured from job creation to the end state
  search          latency of the global search

Usage (repository root, API and worker running):
  .\\.venv\\Scripts\\python.exe -m Benchmarks.Performance.ApiBenchmark
The uploads are generated WAVs (valid media) in a case titled "[Bench] ...", stored without an analysis run (the
automatic-analysis preference is turned off for them and restored after).
"""

import io
import json
import os
import platform
import statistics
import struct
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx
from PIL import Image

API = os.environ.get("NEXTRON_API", "http://127.0.0.1:8001/api/v1")
OUT = Path(__file__).resolve().parents[1] / "Results" / "performance.json"


def pct(values, p):
    s = sorted(values)
    return round(s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))] * 1000, 1)


def latency(client_factory, url: str, *, concurrency: int, requests: int) -> dict:
    def one(_):
        with client_factory() as c:
            t = time.perf_counter()
            r = c.get(url)
            r.raise_for_status()
            return time.perf_counter() - t
    with ThreadPoolExecutor(concurrency) as pool:
        times = list(pool.map(one, range(requests)))
    return {"concurrency": concurrency, "requests": requests, "p50_ms": pct(times, 50), "p95_ms": pct(times, 95), "max_ms": round(max(times) * 1000, 1)}


def wav(path: Path, megabytes: int) -> None:
    rate, frames = 48000, megabytes * 1024 * 1024 // 4
    with open(path, "wb") as f:
        data = frames * 4
        f.write(b"RIFF" + struct.pack("<I", 36 + data) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 2, rate, rate * 4, 4, 16))
        f.write(b"data" + struct.pack("<I", data))
        block = os.urandom(1024 * 1024)
        written = 0
        while written < data:
            n = min(len(block), data - written)
            f.write(block[:n])
            written += n


def main() -> None:
    results: dict = {"measured_at": datetime.now(timezone.utc).isoformat(), "api": API, "machine": {
        "platform": platform.platform(), "processor": platform.processor(), "cpus": os.cpu_count(), "python": platform.python_version()}}
    factory = lambda: httpx.Client(timeout=120)  # noqa: E731
    with factory() as c:
        counts = {"cases": c.get(f"{API}/cases?page_size=1").json()["pagination"]["total_items"],
                  "evidence": c.get(f"{API}/evidence?page_size=1").json()["pagination"]["total_items"]}
        results["data_size"] = counts
        case = c.get(f"{API}/cases?page_size=1").json()["data"][0]["case_id"]
        reads = {"GET /cases": f"{API}/cases?page_size=50", "GET /evidence": f"{API}/evidence?page_size=50",
                 "GET /cases/{id}/summary": f"{API}/cases/{case}/summary", "GET /jobs": f"{API}/jobs?page_size=15",
                 "GET /search?q=e2e": f"{API}/search?q=e2e", "GET /health/ready": f"{API}/health/ready"}
        results["reads"] = {name: [latency(factory, url, concurrency=1, requests=40), latency(factory, url, concurrency=16, requests=160)]
                            for name, url in reads.items()}

        bench = c.post(f"{API}/cases", json={"title": "[Bench] performance"}).json()["data"]["case_id"]
        prefs = c.get(f"{API}/preferences").json()["data"]  # uploads only: no analysis runs queued behind them
        version = c.patch(f"{API}/preferences", json={"version": prefs["version"], "preferences": {"analysis": {"auto_analyze_on_upload": False}}}).json()["data"]["version"]
        results["uploads"] = []
        with tempfile.TemporaryDirectory() as tmp:
            for mb in (25, 200):
                path = Path(tmp) / f"bench-{mb}.wav"
                wav(path, mb)
                with open(path, "rb") as f:
                    t = time.perf_counter()
                    r = c.post(f"{API}/cases/{bench}/evidence", files={"file": (path.name, f, "audio/wav")}, timeout=600)
                    secs = time.perf_counter() - t
                r.raise_for_status()
                results["uploads"].append({"megabytes": mb, "seconds": round(secs, 2), "mb_per_s": round(mb / secs, 1),
                                           "sha256_recorded": len(r.json()["data"]["sha256"]) == 64})
        c.patch(f"{API}/preferences", json={"version": version, "preferences": {"analysis": {"auto_analyze_on_upload": prefs["preferences"]["analysis"]["auto_analyze_on_upload"]}}})

        buf = io.BytesIO()
        Image.effect_noise((1024, 768), 50).convert("RGB").save(buf, "JPEG", quality=90)
        runs = []
        for i in range(3):
            up = c.post(f"{API}/cases/{bench}/evidence", files={"file": (f"bench-{i}.jpg", buf.getvalue(), "image/jpeg")}).json()["data"]
            job = up["analysis_job"]["job_id"]
            while (j := c.get(f"{API}/jobs/{job}").json()["data"])["state"] in ("QUEUED", "RUNNING"):
                time.sleep(0.2)
            t0 = datetime.fromisoformat(j["started_at"]); t1 = datetime.fromisoformat(j["finished_at"])  # running time, not queue wait
            runs.append({"state": j["state"], "seconds": round((t1 - t0).total_seconds(), 2), "modules": j["progress"]["planned"]})
        results["image_runs_1024x768"] = runs
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
