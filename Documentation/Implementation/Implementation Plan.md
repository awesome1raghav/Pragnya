# Implementation Plan

The approved plan, divided into ten steps (26 November 2026). The reasoning, phase mapping, ownership tables
and risks are in [Architecture Reconciliation and Revised Plan](Architecture%20Reconciliation%20and%20Revised%20Plan.md).
Each step is started only on request and is complete only when its checks have actually run.

| Step | Scope | Done when | Status |
|---|---|---|---|
| 1 | **Frontend foundation and real data**: pinned deps, `/` → `/dashboard`, `/about`, new `/sources` `/lineage` `/intelligence`, real API layer, case context, system status, job monitor, backend search, honest "not available yet" pages; backend case objectives/category/last activity | Every route loads, deep links and back/forward work, honest states, create → upload → hash → metadata → integrity in the UI, checked with Playwright | **Done** (9/9 Playwright, 91 backend tests) |
| 2 | **Architecture documents and module contracts**: flowcharts stored verbatim, contract types, typed dependency registry, migration `0004` | `0004` upgrades and downgrades on an empty database; registry tests match the flowchart edge for edge with no cycles | **Done** (134 backend tests, 9/9 Playwright) |
| 3 | **T-MIR orchestration core**: Job Service, worker, planner, leases, retry, cancel, timeout, outbox, WebSocket, NEX-MET moved into T-MIR; Job / Analysis / T-MIR APIs; notifications | 202 job, worker runs it, live events, crash recovery without duplicates, image-only runs skip AUD/VID | Not started |
| 4 | **Media intelligence** (NEX-MET complete, IMG, VID, AUD, PRV) with a documented detector comparison | Real results or explicit UNAVAILABLE for each engine | Not started |
| 5 | **Origin and circulation** (NEX-SRC, FPM, MOC) + Neo4j and Qdrant projections; `/sources`, `/lineage` | SSRF tests, fingerprint precision/recall on a controlled set, projection rebuild | Not started |
| 6 | **Correlation** (NEX-ALN, TRN, CMC) on a controlled ground-truth set | Offsets/trims/splices recovered within stated tolerance | Not started |
| 7 | **Investigation intelligence** (NEX-EGC, REC, INV, RPT); graph, timeline, review, reports pages | Traceable graph, separate reviews, versioned reports | Not started |
| 8 | **Remaining integration**: search of sources/findings/reports, notifications, settings, connection recovery | Multi-tab reconnect and reconciliation | Not started |
| 9 | **Validation and hardening**: security, reliability, performance, backup, Dockerfiles, CI | Suites green on a clean runner | Not started |
| 10 | **UI/UX refinement**: Playwright and screenshot audit | Findings fixed and re-verified | Not started |
