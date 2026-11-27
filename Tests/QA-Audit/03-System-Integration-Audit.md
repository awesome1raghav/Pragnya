# Part 3 — System Integration Audit

Case `5f9a809e-281f-4a5d-adc3-82070ebc3f8c`; 13 preserved fixtures; source discovery excluded. Report generation used only two isolated REPORT_GENERATION jobs.

## Observed system checks

24/24 browser routes loaded; 65 OpenAPI paths; WebSocket replay connected; CORS and WebSocket bad origins rejected. Peak memory, fault injection, full control inventory, and Neo4j recovery were not verified.

## TC-16 — NEX-REC

**MODULE ID:** NEX-REC

**MODULE NAME:** Timeline and Reconstruction

**TEST CASE ID:** TC-16

**PURPOSE:** Validate connected investigation output

**INPUT FIXTURES:** ['NEXTRON-QA-001']

**PRECONDITIONS:** Part 1-2 persisted case and findings

**EXECUTION STEPS:** ['Read reconstruction', 'Record review revisions', 'Generate reports through isolated worker', 'Download PDF and JSON']

**EXPECTED OUTPUT:** Persisted, traceable human investigation output

**ACTUAL OUTPUT:** 4 verified features

**FEATURE VALIDATION TABLE:**

| Feature | Expected behavior | Actual behavior | Verification evidence | Status |
|---|---|---|---|---|
| timeline generation | traceable persisted behavior | 13 ordered received events | 03-Raw-Review-Report-Results.json | PASS |
| event ordering | traceable persisted behavior | ISO timestamps ascending | 03-Raw-Review-Report-Results.json | PASS |
| measured/claimed distinction | traceable persisted behavior | RECEIVED labelled NEXTRON measured | 03-Raw-Review-Report-Results.json | PASS |
| source publication timestamps | traceable persisted behavior | no local source records; Source Finder excluded | 03-Raw-Review-Report-Results.json | BLOCKED |
| alternative hypotheses | traceable persisted behavior | not exercised | 03-Raw-Review-Report-Results.json | BLOCKED |
| persistence | traceable persisted behavior | reconstruction API returned persisted result | 03-Raw-Review-Report-Results.json | PASS |

**FRONTEND STATUS:** Route rendered; action controls not exercised

**API STATUS:** Executed against isolated API

**BACKEND STATUS:** Worker claimed only queued report jobs

**DATABASE STORAGE STATUS:** Reports and reviews persisted; hashes checked

**ALGORITHM MODEL STATUS:** Uses stored findings without new inference

**ERROR HANDLING STATUS:** Negative report failure not injected

**EXECUTION TIME:** [None, None, None, None, None]

**PEAK MEMORY:** None

**FAILED ASSERTIONS:** []

**ROOT CAUSE:** None

**AFFECTED FILES AND FUNCTIONS:** []

**SEVERITY:** MEDIUM

**RECOMMENDED FIX:** Complete blocked controls and failure cases

**FINAL MODULE VERDICT:** PARTIAL

## TC-17 — NEX-INV

**MODULE ID:** NEX-INV

**MODULE NAME:** Review and Decision

**TEST CASE ID:** TC-17

**PURPOSE:** Validate connected investigation output

**INPUT FIXTURES:** ['NEXTRON-QA-001']

**PRECONDITIONS:** Part 1-2 persisted case and findings

**EXECUTION STEPS:** ['Read reconstruction', 'Record review revisions', 'Generate reports through isolated worker', 'Download PDF and JSON']

**EXPECTED OUTPUT:** Persisted, traceable human investigation output

**ACTUAL OUTPUT:** 4 verified features

**FEATURE VALIDATION TABLE:**

| Feature | Expected behavior | Actual behavior | Verification evidence | Status |
|---|---|---|---|---|
| four decisions | traceable persisted behavior | four finding decisions and one case conclusion | 03-Raw-Review-Report-Results.json | PASS |
| review revisions | traceable persisted behavior | finding versions 1..4 | 03-Raw-Review-Report-Results.json | PASS |
| rationale and reviewer | traceable persisted behavior | stored review responses | 03-Raw-Review-Report-Results.json | PASS |
| current/history | traceable persisted behavior | two current subjects, five versions | 03-Raw-Review-Report-Results.json | PASS |
| machine finding unchanged | traceable persisted behavior | pre/post database payload comparison not captured | 03-Raw-Review-Report-Results.json | BLOCKED |
| frontend controls | traceable persisted behavior | route rendered; review actions not clicked | 03-Raw-Review-Report-Results.json | BLOCKED |

**FRONTEND STATUS:** Route rendered; action controls not exercised

**API STATUS:** Executed against isolated API

**BACKEND STATUS:** Worker claimed only queued report jobs

**DATABASE STORAGE STATUS:** Reports and reviews persisted; hashes checked

**ALGORITHM MODEL STATUS:** Uses stored findings without new inference

**ERROR HANDLING STATUS:** Negative report failure not injected

**EXECUTION TIME:** [None, None, None, None, None]

**PEAK MEMORY:** None

**FAILED ASSERTIONS:** []

**ROOT CAUSE:** None

**AFFECTED FILES AND FUNCTIONS:** []

**SEVERITY:** MEDIUM

**RECOMMENDED FIX:** Complete blocked controls and failure cases

**FINAL MODULE VERDICT:** PARTIAL

## TC-18 — NEX-RPT

**MODULE ID:** NEX-RPT

**MODULE NAME:** Reporting

**TEST CASE ID:** TC-18

**PURPOSE:** Validate connected investigation output

**INPUT FIXTURES:** ['NEXTRON-QA-001']

**PRECONDITIONS:** Part 1-2 persisted case and findings

**EXECUTION STEPS:** ['Read reconstruction', 'Record review revisions', 'Generate reports through isolated worker', 'Download PDF and JSON']

**EXPECTED OUTPUT:** Persisted, traceable human investigation output

**ACTUAL OUTPUT:** 6 verified features

**FEATURE VALIDATION TABLE:**

| Feature | Expected behavior | Actual behavior | Verification evidence | Status |
|---|---|---|---|---|
| draft and final | traceable persisted behavior | two generated versions | 03-Raw-Review-Report-Results.json | PASS |
| PDF/JSON byte integrity | traceable persisted behavior | download SHA-256 equals header | 03-Raw-Review-Report-Results.json | PASS |
| PDF readability | traceable persisted behavior | PDF signature and pdfinfo parsed; text extraction unavailable | 03-Raw-Review-Report-Results.json | PASS |
| evidence inventory | traceable persisted behavior | 13 preserved items in both JSON reports | 03-Raw-Review-Report-Results.json | PASS |
| module results | traceable persisted behavior | 84 persisted module result entries | 03-Raw-Review-Report-Results.json | PASS |
| human review separation | traceable persisted behavior | current reviews separate from findings | 03-Raw-Review-Report-Results.json | PASS |
| failed report recovery | traceable persisted behavior | no failure injection | 03-Raw-Review-Report-Results.json | BLOCKED |
| report UI controls | traceable persisted behavior | route rendered, controls untested | 03-Raw-Review-Report-Results.json | BLOCKED |

**FRONTEND STATUS:** Route rendered; action controls not exercised

**API STATUS:** Executed against isolated API

**BACKEND STATUS:** Worker claimed only queued report jobs

**DATABASE STORAGE STATUS:** Reports and reviews persisted; hashes checked

**ALGORITHM MODEL STATUS:** Uses stored findings without new inference

**ERROR HANDLING STATUS:** Negative report failure not injected

**EXECUTION TIME:** [None, None, None, None, None]

**PEAK MEMORY:** None

**FAILED ASSERTIONS:** []

**ROOT CAUSE:** None

**AFFECTED FILES AND FUNCTIONS:** []

**SEVERITY:** MEDIUM

**RECOMMENDED FIX:** Complete blocked controls and failure cases

**FINAL MODULE VERDICT:** PARTIAL

## SYS-01

| Feature | Status | Evidence |
|---|---|---|
| full pipeline | PASS | 13 uploaded assets, persisted module results, human review and reports |
| dependencies | PASS | Part 1 run plan and executions persisted |
| worker retry/crash | BLOCKED | not injected; shared queue risk from Part 1 |

## SYS-02

| Feature | Status | Evidence |
|---|---|---|
| route availability | PASS | 24 of 24 inventoried routes returned 200 |
| controls | BLOCKED | inventory captured buttons/links/inputs; not all actions executed |
| source page | BLOCKED | page rendered; Source Finder controls not activated |

## SYS-03

| Feature | Status | Evidence |
|---|---|---|
| OpenAPI inventory | PASS | 65 paths found |
| request validation | PASS | page=0 returned 422 |
| WebSocket replay | PASS | real case events received |
| authorization | FAIL | no authentication or resource authorization in local single-operator mode |

## SYS-04

| Feature | Status | Evidence |
|---|---|---|
| PostgreSQL/storage | PASS | live probes passed |
| Qdrant | PASS | 15 PostgreSQL embeddings and 15 Qdrant points |
| Neo4j | BLOCKED | disabled in isolated API; projection consistency unverified |
| outbox | BLOCKED | replay observed, projection failure/rebuild not tested |

## SYS-05

| Feature | Status | Evidence |
|---|---|---|
| invalid ID/error | PASS | missing case 404 |
| CORS | PASS | untrusted origin denied |
| WebSocket origin | PASS | untrusted origin rejected |
| authentication | FAIL | local API has no sign-in or resource-level authorization |
| outage/crash recovery | BLOCKED | no Part 3 fault injection |

## SYS-06

| Feature | Status | Evidence |
|---|---|---|
| API latency | PASS | single-sample ready/database/graph timings in raw system results |
| frontend route load | PASS | 24 single-sample route timings in route inventory |
| peak CPU/RAM | BLOCKED | not measured |
| repeatability | BLOCKED | no repeated benchmark series |
