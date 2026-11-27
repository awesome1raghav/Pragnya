# Part 2 — Intelligence and Correlation Audit

Case `5f9a809e-281f-4a5d-adc3-82070ebc3f8c`; run `1d193b46-232f-4ab4-a3bf-e6e820fd151c` (`PARTIALLY_COMPLETED`). NEX-SRC and external discovery were not invoked in Part 2.

## Summary

{
  "modules_tested": 6,
  "feature_assertions_defined": 82,
  "executed": 35,
  "passed": 28,
  "failed": 7,
  "blocked": 44,
  "partial": 3,
  "verified_feature_coverage": 0.427,
  "pass_rate_of_executed": 0.8,
  "critical_issues": [
    "Unrelated solid-color image/video false lineage candidate",
    "Audio alignment of trimmed VID-03 reports 0s where video reports -2s",
    "Controlled audio replacement produces no CMC finding",
    "Graph API snapshot differs from latest run's graph result"
  ]
}

Run result snapshots and current graph API disagree by one node and one edge. This is a reproducible observation, not proof of why the snapshot selection differs.

## TC-10 — NEX-FPM

**MODULE ID:** NEX-FPM

**MODULE NAME:** Fingerprint and Similarity

**TEST CASE ID:** TC-10

**PURPOSE:** Controlled intelligence and correlation validation

**INPUT FIXTURES:** ['NEXTRON-QA-001 shared 13 preserved media items']

**PRECONDITIONS:** Part 1 case, persisted run and local-only corpus

**EXECUTION STEPS:** ['Inspect actual module envelope and API', 'Compare labeled related and unrelated pairs', 'Inspect case-scoped frontend where available']

**EXPECTED OUTPUT:** Traceable input-dependent results matching controlled transformations

**ACTUAL OUTPUT:** 31 persisted findings; states ['COMPLETED', 'COMPLETED', 'COMPLETED', 'COMPLETED', 'COMPLETED', 'COMPLETED']

**FEATURE VALIDATION TABLE:**

| Feature | Expected behavior | Actual behavior | Verification evidence | Status |
|---|---|---|---|---|
| exact hash matching | Match fixture truth or state a limitation | 13 recorded SHA-256 values match fixture manifest | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| perceptual image hashes | Match fixture truth or state a limitation | IMG-01/03 candidate similarity 0.9375; pHash distance 4 | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| video fingerprints | Match fixture truth or state a limitation | VID-01/03 share 10 sampled frames; offset -2s | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| audio fingerprints | Match fixture truth or state a limitation | AUD-01/02 SHARED_AUDIO candidate | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| real embedding inference | Match fixture truth or state a limitation | local SigLIP2/Qdrant query returned input-dependent scores | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| Qdrant indexing and retrieval | Match fixture truth or state a limitation | status: 15 PostgreSQL records and 15 Qdrant points; case query returned four images | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| candidate ranking/top-K | Match fixture truth or state a limitation | IMG-01: self 1.0, IMG-03 0.980025, IMG-02 0.951069 | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| unrelated rejection | Match fixture truth or state a limitation | IMG-04↔VID-04 unrelated solid colors became FRAME_OF_VIDEO candidate, similarity 0.8125 | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | FAIL |
| case boundary | Match fixture truth or state a limitation | search response scope=case; cross-case rejection not exercised | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PARTIAL |
| score semantics | Match fixture truth or state a limitation | raw cosine scores returned; no calibrated probability claim; no acceptance threshold shown | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PARTIAL |
| similarity thresholds | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| duplicate matching | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| crop robustness | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| empty corpus | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| index persistence after restart | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| search filters | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| search latency | Functional and traceable | Not independently executed | No observation captured | BLOCKED |

**FRONTEND STATUS:** Lineage and graph rendered; module-specific controls only where stated in table

**API STATUS:** GET /runs, /analyses, /lineage, /graph; POST local visual-search only

**BACKEND STATUS:** Persisted executor results inspected; no worker launched in Part 2

**DATABASE STORAGE STATUS:** PostgreSQL results; Qdrant local status; Neo4j not verified

**ALGORITHM MODEL STATUS:** See features and raw result envelopes

**ERROR HANDLING STATUS:** Unrelated-control and missing-input behavior recorded

**EXECUTION TIME:** [410, 394, 380, 306, 298, 306]

**PEAK MEMORY:** None

**FAILED ASSERTIONS:** ['unrelated rejection']

**ROOT CAUSE:** See failed feature rows; no product code modified

**AFFECTED FILES AND FUNCTIONS:** []

**SEVERITY:** HIGH

**RECOMMENDED FIX:** Investigate failed pair handling and rerun controlled assertions

**FINAL MODULE VERDICT:** PARTIAL

## TC-11 — NEX-MOC

**MODULE ID:** NEX-MOC

**MODULE NAME:** Media Lineage

**TEST CASE ID:** TC-11

**PURPOSE:** Controlled intelligence and correlation validation

**INPUT FIXTURES:** ['NEXTRON-QA-001 shared 13 preserved media items']

**PRECONDITIONS:** Part 1 case, persisted run and local-only corpus

**EXECUTION STEPS:** ['Inspect actual module envelope and API', 'Compare labeled related and unrelated pairs', 'Inspect case-scoped frontend where available']

**EXPECTED OUTPUT:** Traceable input-dependent results matching controlled transformations

**ACTUAL OUTPUT:** 15 persisted findings; states ['COMPLETED']

**FEATURE VALIDATION TABLE:**

| Feature | Expected behavior | Actual behavior | Verification evidence | Status |
|---|---|---|---|---|
| candidate generation and persistence | Match fixture truth or state a limitation | 15 candidate relationships with UUIDs returned from lineage API | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| known derivative grouping | Match fixture truth or state a limitation | IMG-01/03 and VID-01/02/03 have candidate edges | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| relationship direction | Match fixture truth or state a limitation | earlier_observed=null without claimed publication time | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| unrelated-pair rejection | Match fixture truth or state a limitation | IMG-04↔VID-04 candidate despite unrelated fixture truth | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | FAIL |
| supporting references | Match fixture truth or state a limitation | each edge has evidence IDs, method and distances | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| frontend visualization | Match fixture truth or state a limitation | Lineage.png renders case candidates and uncertainty labels | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| version comparison controls | Match fixture truth or state a limitation | controls not exercised | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | BLOCKED |
| earliest appearance | Match fixture truth or state a limitation | no local source records supplied | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | BLOCKED |
| shared segment identification | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| conflicting timestamps | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| uncertainty calibration | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| frontend comparison controls | Functional and traceable | Not independently executed | No observation captured | BLOCKED |

**FRONTEND STATUS:** Lineage and graph rendered; module-specific controls only where stated in table

**API STATUS:** GET /runs, /analyses, /lineage, /graph; POST local visual-search only

**BACKEND STATUS:** Persisted executor results inspected; no worker launched in Part 2

**DATABASE STORAGE STATUS:** PostgreSQL results; Qdrant local status; Neo4j not verified

**ALGORITHM MODEL STATUS:** See features and raw result envelopes

**ERROR HANDLING STATUS:** Unrelated-control and missing-input behavior recorded

**EXECUTION TIME:** [59]

**PEAK MEMORY:** None

**FAILED ASSERTIONS:** ['unrelated-pair rejection']

**ROOT CAUSE:** See failed feature rows; no product code modified

**AFFECTED FILES AND FUNCTIONS:** []

**SEVERITY:** HIGH

**RECOMMENDED FIX:** Investigate failed pair handling and rerun controlled assertions

**FINAL MODULE VERDICT:** PARTIAL

## TC-12 — NEX-ALN

**MODULE ID:** NEX-ALN

**MODULE NAME:** Temporal Alignment

**TEST CASE ID:** TC-12

**PURPOSE:** Controlled intelligence and correlation validation

**INPUT FIXTURES:** ['NEXTRON-QA-001 shared 13 preserved media items']

**PRECONDITIONS:** Part 1 case, persisted run and local-only corpus

**EXECUTION STEPS:** ['Inspect actual module envelope and API', 'Compare labeled related and unrelated pairs', 'Inspect case-scoped frontend where available']

**EXPECTED OUTPUT:** Traceable input-dependent results matching controlled transformations

**ACTUAL OUTPUT:** 15 persisted findings; states ['COMPLETED']

**FEATURE VALIDATION TABLE:**

| Feature | Expected behavior | Actual behavior | Verification evidence | Status |
|---|---|---|---|---|
| video offset | Match fixture truth or state a limitation | VID-01/03 video offset -2.0s; expected -2.0 ±0.5s | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| frame overlap | Match fixture truth or state a limitation | VID-01 2..11s aligns VID-03 0..9s, RMS 0.0s | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| audio offset | Match fixture truth or state a limitation | VID-01/03 audio offset 0.0s conflicts with known 2s trim; BER 0.2952 near threshold 0.3 | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | FAIL |
| spatial scaling | Match fixture truth or state a limitation | IMG-01/03 scale 0.5x0.5 | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| unrelated rejection | Match fixture truth or state a limitation | unrelated IMG-04/VID-04 candidate inherited from FPM | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | FAIL |
| speed change | Match fixture truth or state a limitation | no speed-change fixture | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | BLOCKED |
| persistence | Match fixture truth or state a limitation | 15 ALIGNMENT findings in result envelope | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| frontend alignment view | Match fixture truth or state a limitation | not exercised | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | BLOCKED |
| added/removed portions | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| different frame rates | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| missing segments | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| confidence calibration | Functional and traceable | Not independently executed | No observation captured | BLOCKED |

**FRONTEND STATUS:** Lineage and graph rendered; module-specific controls only where stated in table

**API STATUS:** GET /runs, /analyses, /lineage, /graph; POST local visual-search only

**BACKEND STATUS:** Persisted executor results inspected; no worker launched in Part 2

**DATABASE STORAGE STATUS:** PostgreSQL results; Qdrant local status; Neo4j not verified

**ALGORITHM MODEL STATUS:** See features and raw result envelopes

**ERROR HANDLING STATUS:** Unrelated-control and missing-input behavior recorded

**EXECUTION TIME:** [143]

**PEAK MEMORY:** None

**FAILED ASSERTIONS:** ['audio offset', 'unrelated rejection']

**ROOT CAUSE:** See failed feature rows; no product code modified

**AFFECTED FILES AND FUNCTIONS:** []

**SEVERITY:** HIGH

**RECOMMENDED FIX:** Investigate failed pair handling and rerun controlled assertions

**FINAL MODULE VERDICT:** PARTIAL

## TC-13 — NEX-TRN

**MODULE ID:** NEX-TRN

**MODULE NAME:** Transformation Analysis

**TEST CASE ID:** TC-13

**PURPOSE:** Controlled intelligence and correlation validation

**INPUT FIXTURES:** ['NEXTRON-QA-001 shared 13 preserved media items']

**PRECONDITIONS:** Part 1 case, persisted run and local-only corpus

**EXECUTION STEPS:** ['Inspect actual module envelope and API', 'Compare labeled related and unrelated pairs', 'Inspect case-scoped frontend where available']

**EXPECTED OUTPUT:** Traceable input-dependent results matching controlled transformations

**ACTUAL OUTPUT:** 18 persisted findings; states ['COMPLETED']

**FEATURE VALIDATION TABLE:**

| Feature | Expected behavior | Actual behavior | Verification evidence | Status |
|---|---|---|---|---|
| resize | Match fixture truth or state a limitation | five RESIZED findings; IMG-01/03 scale 0.5x0.5 | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| re-encoding | Match fixture truth or state a limitation | ten RE_ENCODED findings | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| trim | Match fixture truth or state a limitation | VID-01/03 TRIMMED, shared original span 2..11s | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| audio replacement | Match fixture truth or state a limitation | no audio-replacement finding for VID-03 despite controlled replacement 4..7s | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | FAIL |
| crop | Match fixture truth or state a limitation | no cropped image fixture | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | BLOCKED |
| editing localization | Match fixture truth or state a limitation | not observed in this run | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | BLOCKED |
| malicious intent avoided | Match fixture truth or state a limitation | findings state transformations without intent claims | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| persistence | Match fixture truth or state a limitation | 18 findings in result envelope | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| frontend transformation view | Match fixture truth or state a limitation | not exercised | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | BLOCKED |
| compression parameters | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| frame editing | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| segment insertion | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| combined transformations | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| sequence hypotheses | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| alternative explanations | Functional and traceable | Not independently executed | No observation captured | BLOCKED |

**FRONTEND STATUS:** Lineage and graph rendered; module-specific controls only where stated in table

**API STATUS:** GET /runs, /analyses, /lineage, /graph; POST local visual-search only

**BACKEND STATUS:** Persisted executor results inspected; no worker launched in Part 2

**DATABASE STORAGE STATUS:** PostgreSQL results; Qdrant local status; Neo4j not verified

**ALGORITHM MODEL STATUS:** See features and raw result envelopes

**ERROR HANDLING STATUS:** Unrelated-control and missing-input behavior recorded

**EXECUTION TIME:** [123]

**PEAK MEMORY:** None

**FAILED ASSERTIONS:** ['audio replacement']

**ROOT CAUSE:** See failed feature rows; no product code modified

**AFFECTED FILES AND FUNCTIONS:** []

**SEVERITY:** HIGH

**RECOMMENDED FIX:** Investigate failed pair handling and rerun controlled assertions

**FINAL MODULE VERDICT:** PARTIAL

## TC-14 — NEX-CMC

**MODULE ID:** NEX-CMC

**MODULE NAME:** Cross-Modal Correlation

**TEST CASE ID:** TC-14

**PURPOSE:** Controlled intelligence and correlation validation

**INPUT FIXTURES:** ['NEXTRON-QA-001 shared 13 preserved media items']

**PRECONDITIONS:** Part 1 case, persisted run and local-only corpus

**EXECUTION STEPS:** ['Inspect actual module envelope and API', 'Compare labeled related and unrelated pairs', 'Inspect case-scoped frontend where available']

**EXPECTED OUTPUT:** Traceable input-dependent results matching controlled transformations

**ACTUAL OUTPUT:** 0 persisted findings; states ['COMPLETED']

**FEATURE VALIDATION TABLE:**

| Feature | Expected behavior | Actual behavior | Verification evidence | Status |
|---|---|---|---|---|
| result persistence | Match fixture truth or state a limitation | COMPLETED result envelope persisted | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| audio replacement correlation | Match fixture truth or state a limitation | zero findings; controlled VID-03 audio interval 4..7s unreported | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | FAIL |
| visual/audio discrepancy | Match fixture truth or state a limitation | upstream detector produced no matching discontinuity finding | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | BLOCKED |
| metadata conflicts | Match fixture truth or state a limitation | not an implemented CMC rule in this run | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | BLOCKED |
| provenance conflicts | Match fixture truth or state a limitation | no signed C2PA fixture | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | BLOCKED |
| missing modality | Match fixture truth or state a limitation | VID-05 audio module skipped as NOT_APPLICABLE; CMC did not invent audio | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| partial analysis | Match fixture truth or state a limitation | envelope lists NEX-VID partial limitation | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| frontend correlation view | Match fixture truth or state a limitation | not exercised | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | BLOCKED |
| raw score preservation | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| confidence aggregation | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| contradictory detectors | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| legitimate dubbing alternative | Functional and traceable | Not independently executed | No observation captured | BLOCKED |

**FRONTEND STATUS:** Lineage and graph rendered; module-specific controls only where stated in table

**API STATUS:** GET /runs, /analyses, /lineage, /graph; POST local visual-search only

**BACKEND STATUS:** Persisted executor results inspected; no worker launched in Part 2

**DATABASE STORAGE STATUS:** PostgreSQL results; Qdrant local status; Neo4j not verified

**ALGORITHM MODEL STATUS:** See features and raw result envelopes

**ERROR HANDLING STATUS:** Unrelated-control and missing-input behavior recorded

**EXECUTION TIME:** [39]

**PEAK MEMORY:** None

**FAILED ASSERTIONS:** ['audio replacement correlation']

**ROOT CAUSE:** See failed feature rows; no product code modified

**AFFECTED FILES AND FUNCTIONS:** []

**SEVERITY:** HIGH

**RECOMMENDED FIX:** Investigate failed pair handling and rerun controlled assertions

**FINAL MODULE VERDICT:** PARTIAL

## TC-15 — NEX-EGC

**MODULE ID:** NEX-EGC

**MODULE NAME:** Evidence Graph Construction

**TEST CASE ID:** TC-15

**PURPOSE:** Controlled intelligence and correlation validation

**INPUT FIXTURES:** ['NEXTRON-QA-001 shared 13 preserved media items']

**PRECONDITIONS:** Part 1 case, persisted run and local-only corpus

**EXECUTION STEPS:** ['Inspect actual module envelope and API', 'Compare labeled related and unrelated pairs', 'Inspect case-scoped frontend where available']

**EXPECTED OUTPUT:** Traceable input-dependent results matching controlled transformations

**ACTUAL OUTPUT:** 1 persisted findings; states ['COMPLETED']

**FEATURE VALIDATION TABLE:**

| Feature | Expected behavior | Actual behavior | Verification evidence | Status |
|---|---|---|---|---|
| evidence nodes | Match fixture truth or state a limitation | 13 fixture evidence IDs occur in graph | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| relationship edges | Match fixture truth or state a limitation | 15 candidate-version edges reported in graph result | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| stable node/edge IDs | Match fixture truth or state a limitation | graph API returns IDs and references | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| case isolation | Match fixture truth or state a limitation | case-scoped API; cross-case data test not executed | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PARTIAL |
| snapshot consistency | Match fixture truth or state a limitation | graph API snapshot 9d6231f5-efa0-4198-923c-0fafc74d399d has 134/214 nodes/edges; latest run result snapshot efa5772c-c80b-4079-a314-f940ea7d3b1c reports 135/215 | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | FAIL |
| frontend selection | Match fixture truth or state a limitation | clicked EVD-0010 and detail panel showed IMG-01.jpg | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | PASS |
| zoom/pan/filter | Match fixture truth or state a limitation | not exercised | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | BLOCKED |
| Neo4j projection | Match fixture truth or state a limitation | disabled in isolated API; no consistency/rebuild drill | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | BLOCKED |
| outbox recovery | Match fixture truth or state a limitation | not exercised | 02-Raw-Intelligence-Results.json; 02-Local-Visual-Search.json; 02-Unrelated-Visual-Search.json; screenshots | BLOCKED |
| graph statistics | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| node expansion | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| projection recovery | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| duplicate prevention | Functional and traceable | Not independently executed | No observation captured | BLOCKED |
| refresh persistence | Functional and traceable | Not independently executed | No observation captured | BLOCKED |

**FRONTEND STATUS:** Lineage and graph rendered; module-specific controls only where stated in table

**API STATUS:** GET /runs, /analyses, /lineage, /graph; POST local visual-search only

**BACKEND STATUS:** Persisted executor results inspected; no worker launched in Part 2

**DATABASE STORAGE STATUS:** PostgreSQL results; Qdrant local status; Neo4j not verified

**ALGORITHM MODEL STATUS:** See features and raw result envelopes

**ERROR HANDLING STATUS:** Unrelated-control and missing-input behavior recorded

**EXECUTION TIME:** [1058]

**PEAK MEMORY:** None

**FAILED ASSERTIONS:** ['snapshot consistency']

**ROOT CAUSE:** See failed feature rows; no product code modified

**AFFECTED FILES AND FUNCTIONS:** []

**SEVERITY:** HIGH

**RECOMMENDED FIX:** Investigate failed pair handling and rerun controlled assertions

**FINAL MODULE VERDICT:** PARTIAL

## Captured artifacts

`02-Raw-Intelligence-Results.json` contains full result envelopes, lineage nodes/edges, and graph nodes/edges. `02-Local-Visual-Search.json` and `02-Unrelated-Visual-Search.json` contain raw local Qdrant rankings. `Lineage.png` and `Graph.png` capture the browser. Part 1 files remain unchanged.

## Limits

The prior E2E database contained older work; Part 2 started API and web only. No worker or source endpoint was started. Neo4j consistency, projection rebuild, determinism reruns, cross-case isolation, and peak memory need separate isolated checks. A controlled dataset verifies these specific operations, not general model accuracy.