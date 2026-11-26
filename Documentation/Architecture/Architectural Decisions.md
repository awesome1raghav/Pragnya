# Architectural Decisions

The decision record. Conflicts C-1 … C-18 and decisions D-1 … D-23 were reconciled and approved on
26 November 2026; the full reasoning is in
[Architecture Reconciliation and Revised Plan](../Implementation/Architecture%20Reconciliation%20and%20Revised%20Plan.md) §3 and §6.
This file lists them briefly and adds the decisions taken while building.

## Approved (26 Nov 2026)

| ID | Decision |
|---|---|
| D-1 | ~~`/` redirects to `/dashboard`~~ **Revised 26 Nov 2026 at the operator's request:** `/` shows the landing page (also at `/about`); the application starts at `/dashboard`, which the landing page links to |
| D-2 | T-MIR executes the 12 modules of flowchart A1; CM, CAP, EVD, SRC, INV, RPT are domain-service owned |
| D-3 | One dependency registry with typed edges, validated on import and tested against A1 |
| D-4 | Control flows from T-MIR; data flows only as persisted, versioned results referenced by ID |
| D-5 | Result envelope per Flowchart B §5.2; confidence null unless calibrated with a stated basis |
| D-6 | Modules may read foundation records (cases, evidence, artifacts) without an edge |
| D-7 | One `analysis_jobs` table; Job Service is the only writer of job state; `FOR UPDATE SKIP LOCKED` claims, leases |
| D-8 | Executions carry an input fingerprint; one COMPLETED execution per module, scope and fingerprint |
| D-9 | Per-evidence, per-pair and per-case module scopes |
| D-10 | Transactional outbox for every service's events; investigation_events remains the audit record |
| D-11 | WebSocket `/ws/events` plus job and case views; resume by sequence; REST stays authoritative |
| D-12 | Neo4j and Qdrant join in Step 5 as projections; perceptual hashes stay in PostgreSQL |
| D-13 | Sources enter by investigator URL; resolution is a SOURCE_RESOLUTION job |
| D-14 | New evidence or sources supersede dependent case-level results and trigger a new plan |
| D-15 | Reviews and decisions are separate, versioned records tied to a finding version |
| D-16 | Reports freeze a snapshot manifest; DRAFT without review, FINAL with it |
| D-17 | Keep Next.js; pin dependency versions |
| D-18 | Replace the frontend mock contract with the backend's real shapes |
| D-19 | Investigation context comes from the address; the last case is offered, never assumed |
| D-20 | Backend search endpoint |
| D-21 | Notifications from outbox events; browser preferences local; system configuration read-only |
| D-22 | Contradictions recorded, never averaged into a verdict |
| D-23 | Partial runs end PARTIALLY_COMPLETED; retry only failed modules |
| — | No `AUD → ALN` edge is added (C-4 accepted as a documented limitation) |

## Taken while building

| Date | Decision | Why |
|---|---|---|
| 26 Nov | PostgreSQL 17.12 in Docker on 127.0.0.1:**5433** | A native PostgreSQL already holds 5432 |
| 26 Nov | Imports rooted at the repository (`Backend.App…`, `Database.PostgreSQL…`); run from the root | One Database package without path hacks |
| 26 Nov | Synchronous SQLAlchemy 2 + psycopg 3 | Simpler for API and worker; blocking work runs in the thread pool |
| 26 Nov | Evidence rows exist only after bytes are preserved and re-verified (status always PRESERVED) | No row can claim preservation that did not happen |
| 26 Nov | Append-only / immutable triggers on events, metadata, results, findings, artifacts, outbox | Custody and findings cannot be rewritten by the application |
| 26 Nov | Case categories `MEDIA_MANIPULATION`, `SYNTHETIC_MEDIA`, `SOURCE_VERIFICATION`, `CONTEXT_VERIFICATION`, `OTHER` | Flowchart B §7.4 asks for a category; reversible default vocabulary |
| 26 Nov | Former mock prototype moved to `Frontend/Web/src/demo/` (not routed) | Preserve its designs without serving fixture data |
| 26 Nov | Unknown analysis types, malformed IDs and report addresses return 404 in `proxy.ts` | A page cannot change its status after streaming begins |
| 26 Nov | `/system/modules` serves the catalogue from the registry | The frontend never hardcodes module status or connectivity |
| 26 Nov | Execution states = Flowchart B's nine + `UNAVAILABLE` | Distinguishes "tool missing" from "not applicable" (C-10) |
| 26 Nov | Edge types: CONDITIONAL edges are needed only when the upstream applies to the same scope; FPM and CMC need at least one media/correlation upstream (`require_any`) | Image-only, audio-only and failed branches never deadlock a run |
| 26 Nov | NEX-AUD applies to audio and video evidence and reports NOT_APPLICABLE itself when a video has no audio | No `VID → AUD` or `MET → AUD` edge exists in A1 |
| 26 Nov | NEX-PRV applicability uses a provisional C2PA format list, to be confirmed against the SDK in Step 4 | The SDK is not installed yet |

## Open questions

| Question | Needed by |
|---|---|
| Deepfake detector models: candidates, licences, CPU accuracy | Step 4 |
| Which source connectors are permitted beyond generic public URLs | Step 5 |
| Report review policy (which findings must be reviewed before FINAL) | Step 7 |
| Rename the on-disk `frontend` folder to `Frontend` to match Git | Any time servers are stopped |
