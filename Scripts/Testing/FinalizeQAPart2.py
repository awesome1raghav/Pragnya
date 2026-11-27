"""Create the six Part 2 module reports from captured, immutable QA observations."""
import json
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parents[2] / "Tests" / "QA-Audit"
raw = json.loads((root / "02-Raw-Intelligence-Results.json").read_text(encoding="utf-8"))
state = json.loads((root / "QA-State.json").read_text(encoding="utf-8"))
by_id = {v["id"]: k for k, v in state["evidence"].items()}
edges = raw["api"]["lineage"]["data"]["edges"]
graph = raw["api"]["graph"]["data"]
findings = {mod: [f for entry in entries if entry["result"] for f in entry["result"]["envelope"].get("findings", [])] for mod, entries in raw["module_results"].items()}
search = json.loads((root / "02-Local-Visual-Search.json").read_text(encoding="utf-8"))["response"]["data"]
unrelated = json.loads((root / "02-Unrelated-Visual-Search.json").read_text(encoding="utf-8"))["response"]["data"]
pair = lambda a,b: next((e for e in edges if {by_id.get(e["evidence_a"]), by_id.get(e["evidence_b"])} == {a,b}), None)
aln = next((f for f in findings["NEX-ALN"] if {by_id.get(i) for i in f["evidence_ids"]} == {"VID-01","VID-03"}), None)
trn = [f for f in findings["NEX-TRN"] if {by_id.get(i) for i in f["evidence_ids"]} == {"VID-01","VID-03"}]
graph_report = findings["NEX-EGC"][0]["measurement"]
actual = {
 "NEX-FPM": {"exact hash matching": ("PASS", "13 recorded SHA-256 values match fixture manifest"), "perceptual image hashes": ("PASS", "IMG-01/03 candidate similarity 0.9375; pHash distance 4"), "video fingerprints": ("PASS", "VID-01/03 share 10 sampled frames; offset -2s"), "audio fingerprints": ("PASS", "AUD-01/02 SHARED_AUDIO candidate"), "real embedding inference": ("PASS", "local SigLIP2/Qdrant query returned input-dependent scores"), "Qdrant indexing and retrieval": ("PASS", "status: 15 PostgreSQL records and 15 Qdrant points; case query returned four images"), "candidate ranking/top-K": ("PASS", "IMG-01: self 1.0, IMG-03 0.980025, IMG-02 0.951069"), "unrelated rejection": ("FAIL", "IMG-04↔VID-04 unrelated solid colors became FRAME_OF_VIDEO candidate, similarity 0.8125"), "case boundary": ("PARTIAL", "search response scope=case; cross-case rejection not exercised"), "score semantics": ("PARTIAL", "raw cosine scores returned; no calibrated probability claim; no acceptance threshold shown")},
 "NEX-MOC": {"candidate generation and persistence": ("PASS", "15 candidate relationships with UUIDs returned from lineage API"), "known derivative grouping": ("PASS", "IMG-01/03 and VID-01/02/03 have candidate edges"), "relationship direction": ("PASS", "earlier_observed=null without claimed publication time"), "unrelated-pair rejection": ("FAIL", "IMG-04↔VID-04 candidate despite unrelated fixture truth"), "supporting references": ("PASS", "each edge has evidence IDs, method and distances"), "frontend visualization": ("PASS", "Lineage.png renders case candidates and uncertainty labels"), "version comparison controls": ("BLOCKED", "controls not exercised"), "earliest appearance": ("BLOCKED", "no local source records supplied")},
 "NEX-ALN": {"video offset": ("PASS", "VID-01/03 video offset -2.0s; expected -2.0 ±0.5s"), "frame overlap": ("PASS", "VID-01 2..11s aligns VID-03 0..9s, RMS 0.0s"), "audio offset": ("FAIL", "VID-01/03 audio offset 0.0s conflicts with known 2s trim; BER 0.2952 near threshold 0.3"), "spatial scaling": ("PASS", "IMG-01/03 scale 0.5x0.5"), "unrelated rejection": ("FAIL", "unrelated IMG-04/VID-04 candidate inherited from FPM"), "speed change": ("BLOCKED", "no speed-change fixture"), "persistence": ("PASS", "15 ALIGNMENT findings in result envelope"), "frontend alignment view": ("BLOCKED", "not exercised")},
 "NEX-TRN": {"resize": ("PASS", "five RESIZED findings; IMG-01/03 scale 0.5x0.5"), "re-encoding": ("PASS", "ten RE_ENCODED findings"), "trim": ("PASS", "VID-01/03 TRIMMED, shared original span 2..11s"), "audio replacement": ("FAIL", "no audio-replacement finding for VID-03 despite controlled replacement 4..7s"), "crop": ("BLOCKED", "no cropped image fixture"), "editing localization": ("BLOCKED", "not observed in this run"), "malicious intent avoided": ("PASS", "findings state transformations without intent claims"), "persistence": ("PASS", "18 findings in result envelope"), "frontend transformation view": ("BLOCKED", "not exercised")},
 "NEX-CMC": {"result persistence": ("PASS", "COMPLETED result envelope persisted"), "audio replacement correlation": ("FAIL", "zero findings; controlled VID-03 audio interval 4..7s unreported"), "visual/audio discrepancy": ("BLOCKED", "upstream detector produced no matching discontinuity finding"), "metadata conflicts": ("BLOCKED", "not an implemented CMC rule in this run"), "provenance conflicts": ("BLOCKED", "no signed C2PA fixture"), "missing modality": ("PASS", "VID-05 audio module skipped as NOT_APPLICABLE; CMC did not invent audio"), "partial analysis": ("PASS", "envelope lists NEX-VID partial limitation"), "frontend correlation view": ("BLOCKED", "not exercised")},
 "NEX-EGC": {"evidence nodes": ("PASS", "13 fixture evidence IDs occur in graph"), "relationship edges": ("PASS", "15 candidate-version edges reported in graph result"), "stable node/edge IDs": ("PASS", "graph API returns IDs and references"), "case isolation": ("PARTIAL", "case-scoped API; cross-case data test not executed"), "snapshot consistency": ("FAIL", f"graph API snapshot {graph['snapshot_id']} has {len(graph['nodes'])}/{len(graph['edges'])} nodes/edges; latest run result snapshot {graph_report['snapshot_id']} reports {graph_report['nodes']}/{graph_report['edges']}"), "frontend selection": ("PASS", "clicked EVD-0010 and detail panel showed IMG-01.jpg"), "zoom/pan/filter": ("BLOCKED", "not exercised"), "Neo4j projection": ("BLOCKED", "disabled in isolated API; no consistency/rebuild drill"), "outbox recovery": ("BLOCKED", "not exercised")},
}
extra = {
 "NEX-FPM": ["similarity thresholds", "duplicate matching", "crop robustness", "empty corpus", "index persistence after restart", "search filters", "search latency"],
 "NEX-MOC": ["shared segment identification", "conflicting timestamps", "uncertainty calibration", "frontend comparison controls"],
 "NEX-ALN": ["added/removed portions", "different frame rates", "missing segments", "confidence calibration"],
 "NEX-TRN": ["compression parameters", "frame editing", "segment insertion", "combined transformations", "sequence hypotheses", "alternative explanations"],
 "NEX-CMC": ["raw score preservation", "confidence aggregation", "contradictory detectors", "legitimate dubbing alternative"],
 "NEX-EGC": ["graph statistics", "node expansion", "projection recovery", "duplicate prevention", "refresh persistence"],
}
names = {"NEX-FPM":"Fingerprint and Similarity", "NEX-MOC":"Media Lineage", "NEX-ALN":"Temporal Alignment", "NEX-TRN":"Transformation Analysis", "NEX-CMC":"Cross-Modal Correlation", "NEX-EGC":"Evidence Graph Construction"}
results = []
for n, mod in enumerate(names, 10):
    rows = [{"feature": f, "expected_behavior": "Match fixture truth or state a limitation", "actual_behavior": detail, "verification_evidence": "02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots", "status": status} for f,(status,detail) in actual[mod].items()]
    rows += [{"feature": f, "expected_behavior": "Functional and traceable", "actual_behavior": "Not independently executed", "verification_evidence": "No observation captured", "status": "BLOCKED"} for f in extra[mod] if f not in actual[mod]]
    execution = raw["module_results"][mod]
    results.append({"module_id":mod,"module_name":names[mod],"test_case_id":f"TC-{n:02d}","purpose":"Controlled intelligence and correlation validation","input_fixtures":["NEXTRON-QA-001 shared 13 preserved media items"],"preconditions":"Part 1 case, persisted run and local-only corpus","execution_steps":["Inspect actual module envelope and API", "Compare labeled related and unrelated pairs", "Inspect case-scoped frontend where available"],"expected_output":"Traceable input-dependent results matching controlled transformations","actual_output":f"{len(findings[mod])} persisted findings; states {[v['execution']['state'] for v in execution]}","feature_validation_table":rows,"frontend_status":"Lineage and graph rendered; module-specific controls only where stated in table","api_status":"GET /runs, /analyses, /lineage, /graph; POST local visual-search only","backend_status":"Persisted executor results inspected; no worker launched in Part 2","database_storage_status":"PostgreSQL results; Qdrant local status; Neo4j not verified","algorithm_model_status":"See features and raw result envelopes","error_handling_status":"Unrelated-control and missing-input behavior recorded","execution_time":[v['execution'].get('duration_ms') for v in execution],"peak_memory":None,"failed_assertions":[r['feature'] for r in rows if r['status']=="FAIL"],"root_cause":"See failed feature rows; no product code modified","affected_files_and_functions":[],"severity":"HIGH" if any(r['status']=="FAIL" for r in rows) else "MEDIUM","recommended_fix":"Investigate failed pair handling and rerun controlled assertions","final_module_verdict":"PARTIAL"})
counts = Counter(r["status"] for m in results for r in m["feature_validation_table"])
executed = counts["PASS"] + counts["FAIL"]
summary = {"modules_tested":6,"feature_assertions_defined":sum(counts.values()),"executed":executed,"passed":counts["PASS"],"failed":counts["FAIL"],"blocked":counts["BLOCKED"],"partial":counts["PARTIAL"],"verified_feature_coverage":round(executed/sum(counts.values()),3),"pass_rate_of_executed":round(counts["PASS"]/executed,3),"critical_issues":["Unrelated solid-color image/video false lineage candidate", "Audio alignment of trimmed VID-03 reports 0s where video reports -2s", "Controlled audio replacement produces no CMC finding", "Graph API snapshot differs from latest run's graph result"]}
document = {"case_id":state["case_id"],"summary":summary,"modules":results,"raw_exports":"02-Raw-Intelligence-Results.json"}
(root/"02-Intelligence-And-Correlation-Results.json").write_text(json.dumps(document,indent=2),encoding="utf-8")
lines=["# Part 2 — Intelligence and Correlation Audit","",f"Case `{state['case_id']}`; run `{state['job_id']}` (`PARTIALLY_COMPLETED`). NEX-SRC and external discovery were not invoked in Part 2.","", "## Summary", "",json.dumps(summary,indent=2),"", "Run result snapshots and current graph API disagree by one node and one edge. This is a reproducible observation, not proof of why the snapshot selection differs.",""]
for m in results:
    lines += [f"## {m['test_case_id']} — {m['module_id']}",""]
    for key,value in m.items():
        if key=="feature_validation_table":
            lines += ["**FEATURE VALIDATION TABLE:**","","| Feature | Expected behavior | Actual behavior | Verification evidence | Status |","|---|---|---|---|---|"]
            for row in value:
                lines.append("| " + " | ".join(str(row[k]).replace("|","/") for k in ("feature","expected_behavior","actual_behavior","verification_evidence","status")) + " |")
            lines.append("")
        else:
            lines += [f"**{key.upper().replace('_',' ')}:** {value}",""]
lines += ["## Captured artifacts", "", "`02-Raw-Intelligence-Results.json` contains full result envelopes, lineage nodes/edges, and graph nodes/edges. `02-Local-Visual-Search.json` and `02-Unrelated-Visual-Search.json` contain raw local Qdrant rankings. `Lineage.png` and `Graph.png` capture the browser. Part 1 files remain unchanged.", "", "## Limits", "", "The prior E2E database contained older work; Part 2 started API and web only. No worker or source endpoint was started. Neo4j consistency, projection rebuild, determinism reruns, cross-case isolation, and peak memory need separate isolated checks. A controlled dataset verifies these specific operations, not general model accuracy."]
(root/"02-Intelligence-And-Correlation-Audit.md").write_text("\n".join(lines),encoding="utf-8")
state["part2"].update({"report":"02-Intelligence-And-Correlation-Audit.md","results":"02-Intelligence-And-Correlation-Results.json","summary":summary})
(root/"QA-State.json").write_text(json.dumps(state,indent=2),encoding="utf-8")
print(json.dumps(summary))
