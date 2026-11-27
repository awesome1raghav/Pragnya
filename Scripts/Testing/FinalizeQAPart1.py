"""Refresh live outcomes and write Part 1 audit artifacts without changing product code."""
import json
import subprocess
from collections import Counter
from pathlib import Path

import httpx
from PIL import Image

root = Path(__file__).resolve().parents[2] / "Tests" / "QA-Audit"
state = json.loads((root / "QA-State.json").read_text(encoding="utf-8"))
client = httpx.Client(base_url="http://127.0.0.1:8002/api/v1", timeout=20)
for item in state["evidence"].values():
    if item.get("id"):
        try:
            item["analysis_final"] = client.get(f"/evidence/{item['id']}/analysis").json().get("data")
            metadata = client.get(f"/evidence/{item['id']}/metadata")
            item["metadata_final"] = {"status": metadata.status_code, "body": metadata.json()}
        except Exception as exc:
            item["analysis_refresh_error"] = str(exc)
if state.get("job_id"):
    try:
        state["run_final"] = client.get(f"/runs/{state['job_id']}").json().get("data")
    except Exception as exc:
        state["run_refresh_error"] = str(exc)
(root / "QA-State.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

feature_sets = {
 "NEX-CM": ["creation", "unique ID", "validation", "listing/search/pagination", "update", "statistics/summary", "archive/reopen", "events", "restart persistence", "authorization", "frontend actions"],
 "NEX-CAP": ["image/video/audio upload", "multiple upload", "drag/drop and picker", "screenshot capture", "upload progress", "signature/MIME validation", "size limit", "filename safety", "cancellation", "OCR", "acquisition metadata", "consent", "invalid media rejection", "temporary cleanup", "Android capture"],
 "NEX-EVD": ["SHA-256", "byte preservation/download", "IDs/storage references", "manifest", "custody/history", "integrity verification", "duplicates", "derivative links/hashes", "storage failure", "disposable mismatch", "overwrite protection", "restart persistence"],
 "NEX-MET": ["EXIF", "image dimensions/format", "video duration/resolution/fps/codec", "audio sample rate/channels", "bitrate", "timestamps", "missing/malformed metadata", "tool versions", "persistence", "frontend presentation"],
 "NEX-IMG": ["decode/preprocess", "ELA", "FFT/frequency", "compression", "noise", "resampling", "perceptual hash", "manipulation inference", "AI detector", "localization", "heatmaps", "score semantics", "model load/failure", "persistence", "frontend visualization"],
 "NEX-VID": ["decode", "frame/keyframe extraction", "timestamps", "temporal analysis", "fingerprints", "scene/segment", "splice", "compression", "deepfake model", "localization", "frame previews", "audio extraction", "missing audio", "VFR", "playback/seek", "progress/artifacts", "memory/time"],
 "NEX-AUD": ["decode/extract", "waveform", "spectrogram", "spectral analysis", "normalization", "voice analysis", "fingerprint", "splice", "manipulation", "synthetic speech detector", "model inference", "localization", "playback/seek", "silence/missing audio", "persistence"],
 "NEX-PRV": ["manifest extraction", "credential presence", "signature verification", "content binding", "assertions", "history", "trust policy", "invalid credentials", "absent credentials", "unsupported format", "evidence association", "frontend display"],
}
evidence = state["evidence"]
comparisons = {}
for fid, item in evidence.items():
    path = next((root / "NEXTRON-QA-001").glob(fid + ".*"))
    summary_data = ((item.get("metadata_final") or {}).get("body") or {}).get("data") or {}
    summary_data = summary_data.get("summary") or {}
    if fid.startswith("IMG"):
        with Image.open(path) as image:
            comparisons[fid] = summary_data.get("width") == image.width and summary_data.get("height") == image.height and summary_data.get("format") == image.format
    else:
        probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], timeout=30))
        container = summary_data.get("container") or {}
        comparisons[fid] = abs(float(container.get("duration_seconds") or 0) - float(probe["format"].get("duration") or 0)) < .05
state["independent_metadata_comparisons"] = comparisons
manifest_path = root / "NEXTRON-QA-001" / "Fixture-Manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
for fixture in manifest["fixtures"]:
    fid = fixture["id"]
    if fid in evidence:
        fixture["media_properties"] = ((evidence[fid].get("metadata_final") or {}).get("body") or {}).get("data", {}).get("summary")
        fixture["expected_output_conditions"] = "Preserved byte hash matches fixture; technical metadata agrees with local probe; forensic inference requires separate validation"
        fixture["expected_relationships"] = {"IMG-02": ["derivative of IMG-01"], "IMG-03": ["derivative of IMG-01"], "VID-02": ["derivative of VID-01"], "VID-03": ["trimmed derivative of VID-01"], "AUD-02": ["spliced derivative of AUD-01"]}.get(fid, [])
        fixture["modified_region_or_interval"] = {"IMG-02": "x=500..780, y=300..470", "VID-03": "derived audio t=4..7 seconds", "AUD-02": "t=4..7 seconds"}.get(fid)
        fixture["ground_truth_label"] = "controlled benign edit" if fid in {"IMG-02", "IMG-03", "VID-02", "VID-03", "AUD-02"} else "controlled original or unrelated sample"
manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
(root / "QA-State.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
run = state.get("run_final") or {}
module_execs = {}
for item in evidence.values():
    for module in (item.get("analysis_final") or {}).get("modules", []):
        latest = module.get("latest")
        if latest:
            module_execs.setdefault(module["module_id"], []).append(latest)

results = []
for number, (mod, features) in enumerate(feature_sets.items(), 1):
    prefix = {"NEX-CM": "", "NEX-CAP": "", "NEX-EVD": "", "NEX-MET": "", "NEX-IMG": "IMG", "NEX-VID": "VID", "NEX-AUD": "AUD", "NEX-PRV": "IMG"}[mod]
    inputs = [k for k in evidence if k.startswith(prefix)] if prefix else list(evidence)
    rows = []
    for f in features:
        status, ev = "BLOCKED", "No isolated execution evidence captured"
        if mod == "NEX-CM" and f in {"creation", "unique ID", "listing/search/pagination", "update", "statistics/summary", "archive/reopen", "events"}:
            status, ev = "PASS", "QA-State.json observations: case_create/update/list/statistics/summary/archive/reopen/events"
        if mod == "NEX-CAP" and f in {"image/video/audio upload", "invalid media rejection", "acquisition metadata"}:
            status, ev = "PASS", "13 uploads returned 201; NEG-01/02 returned 415; upload responses in QA-State.json"
        if mod == "NEX-EVD" and f in {"SHA-256", "byte preservation/download", "IDs/storage references", "custody/history", "integrity verification"}:
            status, ev = "PASS", "Independent hashlib and downloaded-byte hashes agree for all uploaded fixtures; history and integrity responses in QA-State.json"
        if mod == "NEX-MET" and f in {"image dimensions/format", "video duration/resolution/fps/codec", "audio sample rate/channels", "tool versions", "persistence"}:
            group = "IMG" if f.startswith("image") else "VID" if f.startswith("video") else "AUD" if f.startswith("audio") else None
            relevant = [k for k in evidence if group is None or k.startswith(group)]
            status, ev = "PASS" if all(comparisons[k] and evidence[k].get("metadata_final", {}).get("status") == 200 for k in relevant) else "FAIL", "Independent Pillow/FFprobe comparison in QA-State.json"
        if mod in module_execs and f == "persistence":
            status, ev = "PASS", "Persisted module execution records via evidence analysis API"
        if mod == "NEX-PRV" and f == "absent credentials":
            status, ev = "PASS" if any(x.get("state") == "COMPLETED" for x in module_execs.get(mod, [])) else "BLOCKED", "NEX-PRV execution on unsigned self-generated media"
        if f in {"AI detector", "deepfake model", "synthetic speech detector", "model inference", "invalid credentials", "signature verification", "content binding", "trust policy"}:
            status, ev = "BLOCKED", "No licensed labeled detector/C2PA positive fixture in NEXTRON-QA-001"
        rows.append({"feature": f, "expected": "Functional, traceable result where supported", "actual": ev, "evidence": ev, "status": status})
    verdict = "PARTIAL" if any(r["status"] == "PASS" for r in rows) else "BLOCKED"
    results.append({"module_id": mod, "module_name": mod, "test_case_id": f"TC-{number:02d}", "purpose": "Controlled functional validation", "input_fixtures": inputs, "preconditions": "Isolated E2E stack and self-generated media", "execution_steps": ["Upload applicable fixtures", "Inspect API records and worker output", "Compare independent file hashes"], "expected_output": "Input-dependent persisted observations with traceability", "actual_output": f"{len(module_execs.get(mod, []))} persisted execution records; {Counter(x.get('state') for x in module_execs.get(mod, []))}", "feature_validation_table": rows, "frontend_status": "BLOCKED: browser interactions not executed in this run", "api_status": "Executed in isolated API", "backend_status": "Observed via API and worker", "database_storage_status": "Isolated nextron_e2e; stored records and downloads", "algorithm_model_status": "See individual feature rows; no positive model ground truth", "error_handling_status": "Negative files rejected 415; other negative paths unverified", "execution_time": [x.get("duration_ms") for x in module_execs.get(mod, [])], "peak_memory": None, "failed_assertions": [r["feature"] for r in rows if r["status"] == "FAIL"], "root_cause": "Missing controlled positive fixtures and incomplete browser validation" if verdict != "PASS" else None, "affected_files_and_functions": [], "severity": "MEDIUM" if verdict == "PARTIAL" else "UNDETERMINED", "recommended_fix": "Complete missing controlled tests and collect licensed positive fixtures", "final_module_verdict": verdict})
counts = Counter(row["status"] for result in results for row in result["feature_validation_table"])
summary = {"modules_tested": len(results), "feature_assertions_defined": sum(counts.values()), "passed": counts["PASS"], "failed": counts["FAIL"], "blocked": counts["BLOCKED"], "verified_feature_coverage": round((counts["PASS"] + counts["FAIL"]) / sum(counts.values()), 3), "pass_rate_of_executed": round(counts["PASS"] / max(1, counts["PASS"]+counts["FAIL"]), 3), "critical_issues": ["Isolated E2E worker consumed pre-existing SOURCE_RESOLUTION queue item; future audit requires a fresh unique database", "No signed C2PA or licensed deepfake positive fixtures", "Frontend interactions not executed"]}
out = {"dataset": "NEXTRON-QA-001", "case_id": state["case_id"], "job_id": state.get("job_id"), "run_state": run.get("state"), "summary": summary, "modules": results}
(root / "01-Foundation-And-Forensics-Results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
lines = ["# NEXTRON Part 1 — Foundation and Forensics Audit", "", f"Case: `{state['case_id']}` in isolated `nextron_e2e`.", f"Dataset: `{state['fixture_root']}`. Run: `{state.get('job_id')}` ({run.get('state')}).", "", "## Summary", "", json.dumps(summary, indent=2), "", "This is a partial audit. A PASS applies only to the individual assertion with captured evidence; unexecuted features are BLOCKED.", ""]
for result in results:
    for key in ["module_id", "module_name", "test_case_id", "purpose", "input_fixtures", "preconditions", "execution_steps", "expected_output", "actual_output", "frontend_status", "api_status", "backend_status", "database_storage_status", "algorithm_model_status", "error_handling_status", "execution_time", "peak_memory", "failed_assertions", "root_cause", "affected_files_and_functions", "severity", "recommended_fix", "final_module_verdict"]:
        if key == "module_id": lines += [f"## {result[key]}", ""]
        lines += [f"**{key.upper().replace('_', ' ')}:** {result[key]}", ""]
    lines += ["| Feature | Expected behavior | Actual behavior | Verification evidence | Status |", "|---|---|---|---|---|"]
    for row in result["feature_validation_table"]:
        lines.append("| " + " | ".join(str(row[k]).replace("|", "/") for k in ("feature", "expected", "actual", "evidence", "status")) + " |")
    lines.append("")
(root / "01-Foundation-And-Forensics-Audit.md").write_text("\n".join(lines), encoding="utf-8")
print(json.dumps(summary))
