"""Local CPU benchmark of the shortlisted detectors (Documentation/Research/Detector Candidates.md).

Run from the repository root:
    .\\.venv\\Scripts\\python.exe -m Benchmarks.Detectors.RunBenchmark images CommunityForensics   (or Spai)
    .\\.venv\\Scripts\\python.exe -m Benchmarks.Detectors.RunBenchmark speech DF                    (or LA)
One detector per process, so peak memory is that detector's own.

For every item it records the detector's score, the label and the time taken; then it computes ROC AUC, EER,
accuracy and false-positive rate at the model's own 0.5 threshold, TPR at 1 % and 5 % FPR, latency and peak
memory, and the effect of Platt calibration (fitted on one half, measured on the other, split by a stable hash).
Results are written to Benchmarks/Results/<detector>.json (scores included, so every number can be recomputed).
"""

import ctypes
import csv
import hashlib
import io
import json
import random
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "Benchmarks" / "Data"
RESULTS = ROOT / "Benchmarks" / "Results"
SPEECH_PER_CLASS = 400
SEED = 20261126


def peak_memory_mb() -> float | None:
    if sys.platform != "win32":
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    c = Counters()
    c.cb = ctypes.sizeof(c)
    current = ctypes.windll.kernel32.GetCurrentProcess
    current.restype = ctypes.c_void_p  # the pseudo-handle (-1) is truncated without this on 64-bit Windows
    query = ctypes.windll.psapi.GetProcessMemoryInfo
    query.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    if not query(current(), ctypes.byref(c), c.cb):
        return None
    return c.PeakWorkingSetSize / 2**20


def _half(key: str) -> int:
    return int(hashlib.sha256(key.encode()).hexdigest(), 16) % 2


def metrics(labels: np.ndarray, scores: np.ndarray, keys: list[str]) -> dict:
    out: dict = {"n": int(labels.size), "positives": int(labels.sum()), "negatives": int((1 - labels).sum())}
    if labels.min() == labels.max():  # a single generator or real source: how often it is flagged at 0.5
        return out | {"flagged_at_0_5": round(float((scores >= 0.5).mean()), 4), "median_score": round(float(np.median(scores)), 4)}
    fpr, tpr, _ = roc_curve(labels, scores)
    eer_i = int(np.nanargmin(np.abs(fpr - (1 - tpr))))
    predicted = scores >= 0.5
    out |= {
        "roc_auc": round(float(roc_auc_score(labels, scores)), 4),
        "eer": round(float((fpr[eer_i] + 1 - tpr[eer_i]) / 2), 4),
        "accuracy_at_0_5": round(float((predicted == labels.astype(bool)).mean()), 4),
        "false_positive_rate_at_0_5": round(float(predicted[labels == 0].mean()), 4),
        "true_positive_rate_at_0_5": round(float(predicted[labels == 1].mean()), 4),
        "tpr_at_1pct_fpr": round(float(np.interp(0.01, fpr, tpr)), 4),
        "tpr_at_5pct_fpr": round(float(np.interp(0.05, fpr, tpr)), 4),
    }
    # calibration: Platt scaling on the logit of the score, fitted on half A, measured on half B
    halves = np.array([_half(k) for k in keys])
    a, b = halves == 0, halves == 1
    if labels[a].min() != labels[a].max() and labels[b].min() != labels[b].max():
        logit = np.log(np.clip(scores, 1e-7, 1 - 1e-7) / (1 - np.clip(scores, 1e-7, 1 - 1e-7))).reshape(-1, 1)
        platt = LogisticRegression().fit(logit[a], labels[a])
        calibrated = platt.predict_proba(logit[b])[:, 1]
        out["calibration_half_b"] = {"n": int(b.sum()), "ece_raw": ece(labels[b], scores[b]), "ece_platt": ece(labels[b], calibrated),
                                     "accuracy_platt_0_5": round(float(((calibrated >= 0.5) == labels[b].astype(bool)).mean()), 4)}
    return out


def ece(labels: np.ndarray, probs: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (probs >= lo) & (probs < hi) if hi < 1 else (probs >= lo) & (probs <= hi)
        if m.any():
            total += m.mean() * abs(probs[m].mean() - labels[m].mean())
    return round(float(total), 4)


def save(detector, dataset: str, items: list[dict], load_s: float) -> dict:
    labels = np.array([i["label"] for i in items])
    scores = np.array([i["score"] for i in items])
    keys = [i["key"] for i in items]
    seconds = np.array([i["seconds"] for i in items])
    summary = {
        "detector": detector.name, "version_sha256_prefix": detector.version, "licence": detector.licence, "trained_on": detector.trained_on,
        "dataset": dataset, "machine": "Windows 11, AMD Ryzen 7 260, 23 GB RAM, CPU only (8 threads)",
        "load_seconds": round(load_s, 2), "seconds_per_item_mean": round(float(seconds.mean()), 3),
        "seconds_per_item_p95": round(float(np.percentile(seconds, 95)), 3), "peak_working_set_mb": round(peak_memory_mb() or 0, 0),
        "overall": metrics(labels, scores, keys),
    }
    groups = sorted({i["group"] for i in items})
    if len(groups) > 1:
        summary["by_group"] = {g: metrics(labels[[i["group"] == g for i in items]], scores[[i["group"] == g for i in items]],
                                          [i["key"] for i in items if i["group"] == g]) for g in groups}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{detector.name}.json").write_text(json.dumps(summary | {"items": items}, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1), flush=True)
    return summary


def run_images(which: str) -> None:
    import pyarrow.parquet as pq

    from Backend.App.Detectors.ImageDetectors import CommunityForensics, Spai

    rows = []
    for shard in sorted((DATA / "CommunityForensicsEval" / "data").glob("CompEval-*.parquet")):
        for r in pq.read_table(shard, columns=["image_name", "image_data", "label", "model_name", "real_source"]).to_pylist():
            data = r["image_data"]["bytes"] if isinstance(r["image_data"], dict) else r["image_data"]
            rows.append({"key": f"{shard.stem}/{r['image_name']}", "label": int(r["label"]), "data": data,
                         "group": f"fake:{r['model_name']}" if r["label"] else f"real:{r['real_source']}"})
    folder = Path(tempfile.mkdtemp(prefix="nextron-bench-"))
    for i, r in enumerate(rows):
        r["path"] = folder / f"{i}"
        r["path"].write_bytes(r.pop("data"))
    for cls in ({"CommunityForensics": CommunityForensics, "Spai": Spai}[which],):
        t0 = time.perf_counter()
        detector = cls()
        load_s = time.perf_counter() - t0
        # resumable: each scored item is appended to a .partial.jsonl file, and a restarted run skips those
        RESULTS.mkdir(parents=True, exist_ok=True)
        partial = RESULTS / f"{detector.name}.partial.jsonl"
        done = {}
        if partial.exists():
            for line in partial.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    item = json.loads(line)
                    done[item["key"]] = item
        with open(partial, "a", encoding="utf-8") as log:
            for r in rows:
                if r["key"] in done:
                    continue
                t0 = time.perf_counter()
                s = detector.score(r["path"])
                item = {"key": r["key"], "label": r["label"], "group": r["group"], "score": s, "seconds": round(time.perf_counter() - t0, 4),
                        "pixels": _pixels(r["path"])}
                done[r["key"]] = item
                log.write(json.dumps(item) + "\n")
                log.flush()
                print(f"{len(done)}/{len(rows)}", flush=True)
        items = [done[r["key"]] for r in rows]
        save(detector, "CommunityForensics-Eval, 4 of 413 shards (500 images; fakes: DFGAN, GALIP)", items, load_s)
        partial.unlink()


def _pixels(path: Path) -> int:
    from PIL import Image

    with Image.open(path) as im:
        return im.width * im.height


def run_speech(which: str) -> None:
    from Backend.App.Detectors.SpeechDetectors import RATE, SslAasist
    from Backend.App.Utils import MediaDecode

    archive = zipfile.ZipFile(DATA / "InTheWild" / "release_in_the_wild.zip")
    meta = list(csv.DictReader(io.TextIOWrapper(archive.open("release_in_the_wild/meta.csv"), encoding="utf-8")))
    rng = random.Random(SEED)
    picked = rng.sample([m for m in meta if m["label"] == "spoof"], SPEECH_PER_CLASS) + \
        rng.sample([m for m in meta if m["label"] == "bona-fide"], SPEECH_PER_CLASS)
    folder = Path(tempfile.mkdtemp(prefix="nextron-bench-"))
    clips = []
    for m in picked:
        path = folder / m["file"]
        path.write_bytes(archive.read("release_in_the_wild/" + m["file"]))
        samples = MediaDecode.decode_audio(path, "ffmpeg", 60, sample_rate=RATE, max_seconds=10)
        clips.append({"key": m["file"], "label": int(m["label"] == "spoof"), "group": "spoof" if m["label"] == "spoof" else "bona-fide",
                      "speaker": m["speaker"], "samples": samples})
    for variant in (which,):
        t0 = time.perf_counter()
        detector = SslAasist(variant)
        load_s = time.perf_counter() - t0
        items = []
        for c in clips:
            t0 = time.perf_counter()
            s = detector.score_samples(c["samples"])
            items.append({"key": c["key"], "label": c["label"], "group": c["group"], "speaker": c["speaker"], "score": s,
                          "seconds": round(time.perf_counter() - t0, 4)})
        save(detector, f"In-the-Wild (Müller et al. 2022), {SPEECH_PER_CLASS} spoof + {SPEECH_PER_CLASS} bona fide, seed {SEED}", items, load_s)
        del detector


if __name__ == "__main__":
    {"images": run_images, "speech": run_speech}[sys.argv[1]](sys.argv[2])
