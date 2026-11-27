# NEXTRON Final QA Audit

**Verdict: PARTIALLY FUNCTIONAL.** One controlled investigation (`5f9a809e-281f-4a5d-adc3-82070ebc3f8c`) with 13 preserved fixtures was audited across three phases. Source Finder was excluded from intentional test calls. This does not certify general forensic accuracy.

## Readiness metrics

| Metric | Observed |
|---|---:|
| In scope modules | 17 |
| Fully passing modules | 0 |
| Partial modules | 17 |
| Source excluded | 1 |
| Features defined | 209 |
| Passed | 65 |
| Failed | 7 |
| Untested or partial | 137 |
| Module completion rate | 0.0 |
| Executed assertion pass rate | 90.3 |
| Feature verification coverage | 34.4 |
| Verified functional feature rate | 31.1 |
| Frontend routes loaded | 24 |
| Frontend routes checked | 24 |
| Frontend controls total inventoried | 1136 |
| Frontend controls actually exercised | not exhaustively counted |
| Verdict | PARTIALLY FUNCTIONAL |

The 90.3% pass rate applies only to the 72 assertions that were actually executed. Verification coverage is 34.4%; 137 assertions are blocked or partial. The 1,136 frontend control count is appearances across 24 pages, not unique controls or a count of working controls.

## Module matrix

| Module | Features | Executed | Passed | Failed | Blocked | Verdict |
|---|---:|---:|---:|---:|---:|---|
| NEX-CM | 11 | 7 | 7 | 0 | 4 | PARTIAL |
| NEX-CAP | 15 | 3 | 3 | 0 | 12 | PARTIAL |
| NEX-EVD | 12 | 5 | 5 | 0 | 7 | PARTIAL |
| NEX-MET | 10 | 5 | 5 | 0 | 5 | PARTIAL |
| NEX-IMG | 15 | 1 | 1 | 0 | 14 | PARTIAL |
| NEX-VID | 17 | 0 | 0 | 0 | 17 | BLOCKED |
| NEX-AUD | 15 | 1 | 1 | 0 | 14 | PARTIAL |
| NEX-PRV | 12 | 1 | 1 | 0 | 11 | PARTIAL |
| NEX-SRC | 0 | 0 | 0 | 0 | 0 | EXCLUDED |
| NEX-FPM | 17 | 8 | 7 | 1 | 9 | PARTIAL |
| NEX-MOC | 12 | 6 | 5 | 1 | 6 | PARTIAL |
| NEX-ALN | 12 | 6 | 4 | 2 | 6 | PARTIAL |
| NEX-TRN | 15 | 6 | 5 | 1 | 9 | PARTIAL |
| NEX-CMC | 12 | 4 | 3 | 1 | 8 | PARTIAL |
| NEX-EGC | 14 | 5 | 4 | 1 | 9 | PARTIAL |
| NEX-REC | 6 | 4 | 4 | 0 | 2 | PARTIAL |
| NEX-INV | 6 | 4 | 4 | 0 | 2 | PARTIAL |
| NEX-RPT | 8 | 6 | 6 | 0 | 2 | PARTIAL |

## System cases

| Case | Verified | Failed | Blocked | Key observation |
|---|---:|---:|---:|---|
| SYS-01 | 2 | 0 | 1 | 13 uploaded assets, persisted module results, human review and reports |
| SYS-02 | 1 | 0 | 2 | 24 of 24 inventoried routes returned 200 |
| SYS-03 | 3 | 1 | 0 | 65 paths found |
| SYS-04 | 2 | 0 | 2 | live probes passed |
| SYS-05 | 3 | 1 | 1 | missing case 404 |
| SYS-06 | 2 | 0 | 2 | single-sample ready/database/graph timings in raw system results |

## Confirmed defects and limits

| ID | Priority | Area | Observation |
|---|---|---|---|
| QA-001 | P1 | NEX-FPM/NEX-MOC | IMG-04 and VID-04 unrelated solid-color fixtures become candidate |
| QA-002 | P1 | NEX-ALN | VID-01/03 audio offset 0s while video offset -2s |
| QA-003 | P1 | NEX-TRN/NEX-CMC | VID-03 audio replacement 4-7s not identified or correlated |
| QA-004 | P2 | NEX-EGC | Graph API 134/214 differs from latest EGC result 135/215 |
| QA-005 | P1 | SYS-03/SYS-05 | No authentication or resource-level authorization |

The unauthenticated API is a documented single-operator local mode. It fails multi-user or remotely exposed authorization requirements; it is not evidence of a bypass of an implemented login. The graph snapshot discrepancy needs cause analysis. VID-03 audio replacement and FPM unrelated-pair behavior are confirmed against the controlled fixture truth.

## Evidence and remaining work

Part 1 contains the fixture manifest, hashes, 13 uploads, independent metadata checks and media results. Part 2 contains raw module envelopes, local Qdrant rankings, lineage, alignment and graph exports. Part 3 contains five review revisions, two worker-generated report versions, 24 browser route records, 65 OpenAPI paths, health/CORS/WebSocket responses and performance samples.

No full control click-through, Neo4j rebuild, worker crash, database outage, cross-case authorization, peak CPU/RAM or repeated latency benchmark was performed in Part 3. PDF bytes and hashes were checked; `pdfinfo` parsed the final PDF as 15 pages, but text extraction was unavailable. The prior shared E2E queue claimed an older source job during Part 1; Part 2 and Part 3 started without a general worker, and Part 3 claimed only verified report jobs.

Raw records: `01-Foundation-And-Forensics-Results.json`, `02-Intelligence-And-Correlation-Results.json`, `03-System-Integration-Results.json`, `03-Raw-System-Results.json`, `03-Raw-Review-Report-Results.json`. Reproduce from scripts in `Scripts/Testing/`; preserve `QA-State.json` and the isolated database for follow-up.
