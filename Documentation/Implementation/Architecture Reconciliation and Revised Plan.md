# NEXTRON — Architecture Reconciliation and Revised Development Plan

**Status:** PROPOSED — awaiting approval. Nothing described here as "proposed" has been implemented.
**Date:** 26 November 2026
**Inputs reconciled:**

| Rank | Source | Referred to here as |
|---:|---|---|
| 1 | Latest module connectivity flowchart (12 dotted T-MIR edges, includes `SRC --> MOC`) | **Flowchart A1** |
| 2 | Master prompt: grouped module flowchart (18 dotted T-MIR edges) and application flowchart | **Flowchart A2**, **Flowchart B** |
| 3 | Requirements and technology decisions in the master archive (`Documentation/NEXTRON Master Project Archive.md`) | **Archive** |
| 4 | Repository as inspected on 26 Nov 2026 | **Repo** |
| 5 | Previous Step 0–9 roadmap | **Old roadmap** |

Labels used below: **[ESTABLISHED]** = stated in a ranked source; **[PROPOSED]** = my recommendation, needs approval; **[CONFLICT]** = sources disagree.

---

## 1. Existing repository status

### 1.1 Backend and database (built in Steps 0–2 of the old roadmap, uncommitted)

| Area | What exists | Status |
|---|---|---|
| Environment | Windows 11, Python 3.11.9 venv, Node 24, Docker Desktop 29.9 (Compose v5.7), FFmpeg/FFprobe 9.1, RTX 5050 8 GB, 23 GB RAM | IMPLEMENTED AND VERIFIED |
| PostgreSQL | `Infrastructure/Docker/docker-compose.yml`, PostgreSQL 17.12 on 127.0.0.1:5433 (native PG 17 holds 5432) | IMPLEMENTED AND VERIFIED |
| Migrations | One Alembic history in `Database/PostgreSQL`: `0001` baseline, `0002` cases / evidence / evidence_metadata / investigation_events with append-only and immutable-fact triggers | IMPLEMENTED AND VERIFIED |
| API foundation | FastAPI app factory, `{success,data,meta}` envelope, structured errors, request IDs, CORS for :8080, `/docs` | IMPLEMENTED AND VERIFIED |
| Health | `/health`, `/health/ready` (DB + migrations + storage), `/system/database`, `/system/storage` — all real probes | IMPLEMENTED AND VERIFIED |
| NEX-CM | Cases CRUD, archive/reopen, statistics, summary, cursor events | IMPLEMENTED AND VERIFIED |
| NEX-CAP | Streaming multipart upload, signature + decode validation, size limit, safe filename labels | IMPLEMENTED AND VERIFIED |
| NEX-EVD | Server-side SHA-256, read-only originals, re-verify before commit, custody events, verify-integrity, preview with Range, download, history, reconciliation script | IMPLEMENTED AND VERIFIED |
| NEX-MET | FFprobe and Pillow/EXIF extraction, versioned rows | PARTIALLY IMPLEMENTED — runs inside the upload request (not T-MIR); no XMP, no device/inconsistency analysis |
| Tests | 84 pytest + HTTPX tests against real PostgreSQL, FFprobe and Pillow | IMPLEMENTED AND VERIFIED |
| Jobs, workers, outbox, WebSocket, T-MIR | — | NOT IMPLEMENTED |
| NEX-IMG … NEX-RPT (14 modules) | — | NOT IMPLEMENTED |
| Neo4j, Qdrant | — | NOT IMPLEMENTED (deliberately deferred) |
| Authentication | Single local operator; API bound to 127.0.0.1 | NOT IMPLEMENTED (by design for now) |

### 1.2 Frontend (`Frontend/Web`, owned by Raghav)

- **Stack:** Next.js App Router (`next dev -p 8080`), React, TypeScript, framer-motion, GSAP, lucide-react. All dependencies are `"latest"` (unpinned); a lockfile exists. **Not** the React + Vite + React Router + TanStack Query stack the archive proposed. [ESTABLISHED by repo; preserved — see §6, decision D-17]
- **Data:** every screen reads through one `NextronApi` interface. With `NEXT_PUBLIC_NEXTRON_API` unset, a **mock adapter** serves fixtures with simulated latency; the HTTP adapter targets routes (`/findings`, `/decisions`, `/assessment`, `/activity`, `/audit`, `/models`, `/analysis`) that **do not exist** in the backend or in the archive's API catalogue. The store loads all data at start-up into one context.
- **Contract mismatch:** the frontend contract expects values the backend cannot honestly produce: calibrated `confidence` 0..1 on every finding, per-branch `readiness` percentages, `Assessment` outcome ranges, case `priority` 0..100 with a `reason`, `legalHold`, cover stills/overlays, and audit events with a `signature`/`verified` flag. Its vocabulary (`flagged`, `in_review`, branches `spatial/temporal/audio_visual`) differs from the archive's (`OPEN…ARCHIVED`, modules NEX-IMG/VID/AUD/PRV).
- **Context:** case and evidence come from the URL; pages without one **fall back to "the most urgent case"** — an invented default.
- **Search:** a client-side command palette over already-loaded mock data.
- **Live updates:** none; analysis progress is simulated by a timer in the mock.
- **Build state:** `Frontend/Web` has no `node_modules`; stale `node_modules` and `.next` sit in the old `frontend/` location. The on-disk folder is lowercase `frontend` while Git tracks `Frontend/` (works on Windows only because the filesystem is case-insensitive).

### 1.3 Other repository content

- `Documentation/Backend API Specification.md` and `ML Output Specification.md` describe the **frontend mock contract**, not the archive's contract.
- `Documentation/NEXTRON Master Architecture.md` (teammate) proposes a different engine decomposition (spatial/temporal/audio-visual branches, fusion → classification) and lists frontend/database as "not selected".
- `Infrastructure/Docker/*.Dockerfile` reference a `Backend/Dockerfile` layout and `App.Main` import path that no longer exist.
- `.github/workflows/Backend CI.yml` only installs dependencies; no tests run in CI.

---

## 2. Previous roadmap compared with the new architecture

| Old step | New phase | Assessment |
|---|---|---|
| Step 0 inspect | Phase 00 | Done. Still valid. |
| Step 1 foundation | Phase 02 | Done. Matches. |
| — | **Phase 03 contracts** | **New.** Old roadmap had no explicit module-contract phase; contracts were to emerge inside Step 3. Required before T-MIR. |
| Step 2 CM/CAP/EVD/MET | Phase 04 (+ MET in Phase 06) | CM/CAP/EVD done. **MET moves**: Flowchart A1 makes MET a T-MIR-coordinated module, so its synchronous extraction in the upload request must move into the pipeline. Phase 04 also needs small CM additions (§4). |
| Step 3 jobs/workers/T-MIR | Phase 05 | Same intent; scope expands: dependency registry with cycle detection and applicability, WAITING_FOR_DEPENDENCIES/SKIPPED states, re-execution on evidence change, duplicate prevention, resource classes. |
| Step 4 IMG/VID/AUD/PRV | Phase 06 | Same; MET joins. Model comparison requirement unchanged. |
| Step 5 SRC/FPM/MOC + Qdrant/Neo4j | Phase 07 | Same; **new edge `SRC --> MOC`** must be honoured. |
| Step 6 ALN/TRN/CMC | Phase 08 | Same. |
| Step 7 EGC/REC/INV/RPT | Phase 09 | Same. |
| Step 8 connect frontend | Phases 10 + 11 | Much larger than "adapt the client": three routes are missing, the contract must be replaced, global search / job monitor / status are missing. |
| Step 9 hardening | Phase 12 | Same; testing also continuous. |
| — | **Phase 13 UI/UX refinement** | **New.** Playwright-driven audit of the running UI. |

---

## 3. Identified contradictions

| # | Conflict | Sources | Proposed resolution |
|---|---|---|---|
| C-1 | T-MIR coordinates **12** modules (A1) vs **all 18** (A2, dotted edges to CM, CAP, EVD, SRC, INV, RPT). | A1 vs A2 | A1 ranks higher and the reconciliation prompt says not to assume the six are orchestrated. **[PROPOSED]** T-MIR *executes* the 12; it *observes* the other six through events (§9). A2 is preserved verbatim as a visualization. |
| C-2 | `SRC --> MOC` exists in A1, absent in A2 and in the archive diagram. | A1 vs A2/Archive | A1 wins: the registry includes `SRC → MOC`. |
| C-3 | Archive diagram has `CM --> SRC`, `EVD --> EGC` and `INV -.-> CAP` ("request more evidence"); A1 has none of these. | Archive vs A1 | No module **data** dependency is added. **[PROPOSED]** SRC gets case context as an input record (Q1). EGC reads evidence **records** by reference (allowed reference read, not a module dependency — D-6). "Request more evidence" is an INV action that creates a case task, not a graph edge. |
| C-4 | No `AUD --> ALN` edge, yet the archive says NEX-ALN owns audio alignment and the signature demo aligns audio intervals. | A1 vs Archive §4/§6.4 | **[PROPOSED]** ALN obtains audio alignment inputs through MOC's version pairs and FPM's audio fingerprints (FPM consumes AUD). Documented as a limitation; flag for your decision whether to add `AUD → ALN` (would change A1 — not done). |
| C-5 | No `MET --> CMC` edge, yet the archive lists metadata as a correlation input. | A1 vs Archive §4.14 | Follow A1: MET findings reach correlation only via FPM/MOC. Metadata inconsistencies are reported by MET itself and appear in EGC/report via the case snapshot. Documented. |
| C-6 | No `VID --> IMG` and no `VID --> AUD`; archive had VID extracting frames for IMG and the audio track for AUD. | A1 vs Archive | **[PROPOSED]** IMG analyses IMAGE evidence; VID analyses its own frames; AUD extracts the audio track itself from AUDIO or VIDEO evidence. Shared extraction is an artifact cache, not a module dependency. |
| C-7 | Flowchart B links **Analysis Service ↔ analysis_jobs** but gives **Job Service** no table. | B | **[PROPOSED]** One `analysis_jobs` table (name kept from B) holds all durable jobs with a `job_type`; **Job Service** owns lifecycle (claim, lease, retry, cancel, timeout); Analysis/T-MIR/Source/Report services create jobs through it. |
| C-8 | Flowchart B lists no Review (NEX-INV), Notification, Settings or Search API, and Health APIs have no domain service. | B vs Archive §9 / B §7 | **[PROPOSED]** Add **Review APIs → Review Service**, **Notification APIs**, **Settings/Preferences APIs**, **Search API** as documented additions; Health APIs → existing `HealthService`. |
| C-9 | Flowchart B feeds the Event Publisher only from Job/Analysis/T-MIR services, but B §11 requires events for case creation and evidence acquisition. | B diagram vs B §11 | **[PROPOSED]** All services write to one transactional **outbox**; the publisher reads only the outbox. |
| C-10 | Execution states: B §5.1 (PENDING, QUEUED, WAITING_FOR_DEPENDENCIES, RUNNING, COMPLETED, PARTIALLY_COMPLETED, FAILED, CANCELLED, SKIPPED) vs archive engine states (adds UNAVAILABLE, NOT_STARTED). | B vs Archive | **[PROPOSED]** Use B's nine states **plus UNAVAILABLE** (tool/model not installed or not licensed) because A1-reconciliation requires distinguishing unavailable from inapplicable. SKIPPED always carries a reason code (`NOT_APPLICABLE`, `UPSTREAM_FAILED`, `NO_INPUT`, `SUPERSEDED`). |
| C-11 | `/` must redirect to `/dashboard` (B §7.1) vs the existing marketing landing page at `/` (frontend teammate's work). | B vs Repo | **Needs your decision (D-1).** Options: move landing to `/about` (or a separate site) and redirect `/`; or keep landing and treat it as outside the app shell. |
| C-12 | Archive proposed React + Vite + React Router + TanStack Query + Zustand; repo uses Next.js; B says keep the existing stack. | Archive vs Repo/B | Keep Next.js (D-17). Server state handled with a small query/cache layer; no stack swap. |
| C-13 | Frontend contract demands calibrated confidence, readiness %, outcome ranges, audit signatures. | Repo vs Archive/B §5.2 ("confidence must not be generated arbitrarily") | Replace the frontend contract with the backend's real shapes; fields without an honest source are removed or shown as unavailable (D-18). |
| C-14 | B §18 wants `docs/architecture/module-connectivity.md` etc.; repo convention is `Documentation/` with capitalised, space-separated names. B allows adapting to conventions. | B vs Archive §13 | **[PROPOSED]** `Documentation/Architecture/Module Connectivity.md`, … (§15). |
| C-15 | B §18: "store the **first supplied** flowchart in module-connectivity.md" = A2; A1 is the higher authority. | B vs reconciliation prompt | **[PROPOSED]** `Module Connectivity.md` stores **A1 first (canonical)** and **A2 second (grouped visualization)**, both byte-for-byte as supplied. |
| C-16 | Teammate's `NEXTRON Master Architecture.md` decomposes engines differently (spatial/temporal/AV branches, fusion → classification with verdict labels). | Repo vs A1/Archive | Treat it as research input for NEX-IMG/VID/AUD internals and NEX-CMC; not as module authority. A single "verdict" classification conflicts with archive rules (no fused truth label) — flag to the team. |
| C-17 | B §7.4 asks for investigation **objectives** and **category**; B §7.3 asks for **last activity** in the list. Backend has none. | B vs Repo | Add in Phase 04 delta (migration `0003`). |
| C-18 | Archive lists separate tables per correlation module (`alignment_results`, `transformation_findings`, `correlation_results`); B lists only generic `analysis_results`. | Archive vs B | **[PROPOSED]** Generic `analysis_results` + `analysis_findings` for all modules; dedicated tables only where queries need them (fingerprints, relationships, graph, sources, reviews, reports). |

---

## 4. Missing functionality

**Backend**
- Phase 04 delta: case `objectives`, `category`, `last_activity_at` in list/detail; optional source URL recorded at acquisition.
- Module contract types, dependency registry, execution planner, persistent jobs, worker process, leases/heartbeats, retry/backoff, cancellation, timeouts, outbox, event dispatcher, WebSocket gateway, notification consumer.
- T-MIR, Job, Analysis APIs (`/jobs`, `/cases/{id}/runs`, `/evidence/{id}/analyze`, `/analyses/{id}`, `/tmir/modules`, …).
- 14 modules NEX-IMG … NEX-RPT; NEX-MET re-homed into T-MIR and extended (XMP, device fields, inconsistency checks).
- Source Service with SSRF-safe resolution; Qdrant and Neo4j projections with rebuild/consistency tools.
- Review Service, Report Service (versioned PDF/JSON), Search, Notifications, Settings/Preferences.
- Workers health (`/system/workers`), job queue status, projection lag, module availability (`/system/modules`).

**Frontend**
- Routes `/sources`, `/lineage`, `/intelligence`.
- Real API adapter replacing the mock contract; per-route data loading; loading/empty/error/stale/offline states.
- Explicit active-case context (no "most urgent case" default).
- Global job monitor, global system-status indicator, backend-wide search.
- Live event client with reconnect + REST reconciliation.
- Navigation entries for Sources, Lineage, Intelligence.

---

## 5. Existing functionality to preserve

- All Step 0–2 backend work, its tests, the single Alembic history, the root `Database/` package, `Backend/` layout, PostgreSQL authority, append-only custody triggers, read-only originals, envelope and error contract.
- Frontend: Next.js app, design system (`workspace.module.css`, UI primitives), shell (sidebar, topbar, breadcrumbs, command palette), route tree, evidence workbench tools, graph view, report studio layout, case tab shell, `paths` helper (one place for addresses), the adapter pattern (`NextronApi` interface so screens never call `fetch` directly).
- The archive's technology decisions: FastAPI, Python, PostgreSQL, Docker, Alembic, persistent workers, WebSockets, FFmpeg, Qdrant, Neo4j, protected original storage, PDF + JSON reports.

---

## 6. Proposed architectural decisions

| ID | Decision | Basis |
|---|---|---|
| D-1 | `/` behaviour — **your decision** (C-11). Default if no answer: redirect `/` to `/dashboard` and move the landing page to `/about`, keeping it intact. | B §7.1 |
| D-2 | T-MIR executes exactly the 12 A1 modules; CM/CAP/EVD/SRC/INV/RPT are owned by their domain services (§9). | A1, reconciliation §5 |
| D-3 | **Dependency registry** in one file (`Backend/App/Orchestration/TMir/DependencyRegistry.py`) mirrors A1's solid edges, each typed `REQUIRED`, `CONDITIONAL` or `OPTIONAL` (§8); validated at start-up (unknown IDs, cycles) and by a test that compares it edge-for-edge with A1. | Reconciliation §4 |
| D-4 | **Control vs data:** T-MIR sends control (plan, schedule, cancel) to modules through a standard `ModuleExecutor` interface; modules never call each other; data moves only as **persisted, versioned results referenced by ID** in the execution context. | B §15.10, Archive §5 |
| D-5 | **Result contract:** B §5.2 envelope adopted (`schema_version`, `module_id`, `status`, `input_references`, `findings`, `limitations`, `warnings`, `artifacts`, `dependencies`, `tool_versions`, timings, `errors`). `confidence` stays `null` unless a documented calibration exists; raw scores carry `score_kind` (`METHOD_SPECIFIC`, `DISTANCE`, `SIMILARITY`, `CALIBRATED_PROBABILITY`). Each finding has `assertion` = `OBSERVATION`, `INFERENCE` or `INCONCLUSIVE`. | B §5.2, Archive §5.2 |
| D-6 | Modules may read **foundation records** (case, evidence, artifacts) by reference; this is not a module dependency and is not drawn as one. | A1 interpretation |
| D-7 | **Jobs:** one `analysis_jobs` table, `job_type` ∈ `INVESTIGATION_RUN`, `SOURCE_RESOLUTION`, `REPORT_GENERATION`, `PROJECTION_REBUILD`; Job Service is the only writer of job state; claiming with `FOR UPDATE SKIP LOCKED`, lease + heartbeat, attempts, backoff, cooperative cancel, per-job timeout. | B, Archive §10 |
| D-8 | **Module executions:** `analysis_executions` (one row per module × scope × attempt) with state, reason, timings, tool versions, and an **input fingerprint** = hash(module version + parameters + referenced input result versions + evidence SHA-256). A unique index on (module, scope, input fingerprint, status COMPLETED) prevents duplicate work and lets resumed runs reuse finished results. | Reconciliation §5 |
| D-9 | **Scopes:** per-evidence modules MET, IMG, VID, AUD, PRV (and FPM fingerprint extraction); case-scope modules FPM search, MOC, ALN, TRN, CMC, EGC, REC. A run plans the per-evidence modules for each in-scope evidence item, then the case chain. | A1 + Archive |
| D-10 | **Outbox:** every service writes domain changes and an `outbox_events` row in one transaction; one dispatcher publishes to WebSocket subscribers, the notification consumer and (Phase 07) Neo4j/Qdrant consumers, each with its own checkpoint. Events carry `schema_version`, `event_id`, monotonically increasing `sequence`. Existing `investigation_events` (custody/lifecycle audit) stays and is not the transport. | Archive §11.2, B §11 |
| D-11 | **WebSocket:** `/api/v1/ws/events` (all events visible to the local operator; filters by `case_id`/`job_id`), plus archive's `/ws/jobs/{id}` and `/ws/cases/{id}` as filtered views. Clients resume with `?after=<sequence>`; REST remains authoritative. SSE not added. | Archive §9, B §11 |
| D-12 | **Neo4j and Qdrant** join Compose in Phase 07, when FPM/MOC/EGC produce data to project. Until then the graph API reads PostgreSQL `evidence_nodes/edges`. Perceptual hashes stay in PostgreSQL (Hamming search); Qdrant holds dense embeddings only when an embedding model is adopted. Projections are rebuildable, idempotent, tombstone-aware, and their lag is shown on `/system`. | Archive §11, reconciliation §6 |
| D-13 | **Source Intelligence:** sources enter by investigator URL (`POST /cases/{id}/sources`) or a source URL captured at acquisition; resolution is a `SOURCE_RESOLUTION` job; retrieved bytes re-enter through CAP → EVD as new evidence. T-MIR reads committed source records and re-plans FPM/MOC/EGC when they change. | Q1/Q2 |
| D-14 | **Invalidation:** new evidence or a changed source record marks dependent case-scope results `SUPERSEDED` and triggers a new plan; per-evidence results whose input fingerprint is unchanged are reused. Older results remain readable; reviews and reports keep pointing at the versions they used. | Q11 |
| D-15 | **Review (NEX-INV):** reviews and decisions are separate, versioned records tied to a specific finding/result version; decision enum `ACCEPTED`, `REJECTED`, `INCONCLUSIVE`, `NEEDS_MORE_EVIDENCE`; reviewer identity from the server. Finding-level review possible as soon as findings exist; case-level conclusions require REC to have completed. | Archive §4.17 |
| D-16 | **Reports (NEX-RPT):** `REPORT_GENERATION` job freezes a **snapshot manifest** (evidence SHA-256s, result IDs+versions, review revisions, tool versions); writes immutable JSON + PDF artifacts with their own SHA-256 in `report_versions`. Draft reports allowed without review and labelled DRAFT; FINAL requires a recorded review per policy. Contradictions and limitations sections cannot be switched off. | Archive §4.18, Q12 |
| D-17 | Keep **Next.js**; pin dependency versions from the lockfile (no `latest`). | B §6, Repo |
| D-18 | **Frontend contract:** replace `contract.ts` shapes with types generated from (or hand-mirrored against) the backend OpenAPI; keep the adapter pattern; remove the mock from production builds (keep it only as a labelled test fixture). | B §13, Archive §8 |
| D-19 | **Investigation context:** the URL is authoritative (`/investigations/:caseId/...`, or `?case=<id>` on global routes). The last active case is remembered in session storage and offered as a choice; never silently assumed. | B §7.5, §15.7 |
| D-20 | **Search:** `GET /api/v1/search?q=` across cases, evidence (number, filename, SHA-256 prefix), sources, findings and reports, implemented in PostgreSQL (trigram index when needed). The palette calls it instead of filtering loaded data. | B §8 |
| D-21 | **Notifications:** a consumer turns selected outbox events (job completed/failed, report generated, integrity mismatch, worker down) into `notifications` rows; `GET /notifications`, `PATCH …/read`, `POST /notifications/read-all`. **Settings:** user preferences in a `preferences` table via `/preferences`; system configuration exposed read-only and secret-free via `/system/config`. | Archive §9, B §7.12/7.14 |
| D-22 | **Contradictions:** CMC records `SUPPORTS` / `CONTRADICTS` / `INCONCLUSIVE` relations between findings; nothing averages them into a single verdict; INV must resolve or record INCONCLUSIVE; reports always list open contradictions. | Q13, Archive §17 |
| D-23 | **Partial runs:** a run ends `PARTIALLY_COMPLETED` when any planned module is FAILED/UNAVAILABLE; downstream modules run on what exists and record limitations; `POST /analyses/{id}/retry` re-runs only failed modules. | Q14 |

---

## 7. Revised development roadmap

| Phase | Scope | Current status |
|---|---|---|
| 00 Repository and environment audit | This document §1 | IMPLEMENTED AND VERIFIED |
| 01 Architecture reconciliation | This document; then the architecture documents in §15 | IN PROGRESS (awaiting approval) |
| 02 Backend and database foundation | FastAPI, PostgreSQL, Docker, migrations, storage, config, envelope, health | IMPLEMENTED AND VERIFIED (Dockerfiles and CI still stale → Phase 12) |
| 03 Module communication contracts | Result/finding/artifact/evidence-reference types, execution states, dependency registry, migration `0003` (jobs, executions, results, findings, artifacts, outbox) | NOT IMPLEMENTED |
| 04 Investigation foundation | NEX-CM, NEX-CAP, NEX-EVD | IMPLEMENTED AND VERIFIED, plus delta: objectives, category, last activity |
| 05 T-MIR orchestration core | Job Service, worker, planner, leases, retry, cancel, timeout, outbox, WebSocket, re-home NEX-MET; T-MIR/Job/Analysis APIs | NOT IMPLEMENTED |
| 06 Media intelligence | NEX-MET (complete), IMG, VID, AUD, PRV; documented detector comparison | NOT IMPLEMENTED (MET partial) |
| 07 Origin and circulation | NEX-SRC, FPM, MOC; Qdrant + Neo4j projections | NOT IMPLEMENTED |
| 08 Correlation | NEX-ALN, TRN, CMC on a controlled ground-truth set | NOT IMPLEMENTED |
| 09 Investigation intelligence | NEX-EGC, REC, INV, RPT | NOT IMPLEMENTED |
| 10 Frontend page architecture | 14 routes, shell, nav, context, job monitor, status | PARTIALLY IMPLEMENTED (11 of 14 routes exist, all on mock data) |
| 11 Full-stack integration | Real APIs, search, live events, per-route states | NOT IMPLEMENTED |
| 12 Validation and hardening | Security, reliability, performance, backup, CI, Dockerfiles | NOT IMPLEMENTED (continuous testing already in place) |
| 13 UI/UX refinement | Playwright audit of the running app | NOT IMPLEMENTED |

---

## 8. Module dependency mapping (registry specification)

Edge types: **REQUIRED** — downstream cannot run without a COMPLETED upstream; **CONDITIONAL** — required only when its applicability rule holds for the input; **OPTIONAL** — used when present, otherwise recorded as a limitation. Applicability rules use foundation records (D-6).

| Module | Scope | Applies when | Upstream (A1 edges) and type | If required input is missing |
|---|---|---|---|---|
| NEX-CM | — | always | entry | — |
| NEX-CAP | request | case open | CM: REQUIRED | request rejected |
| NEX-EVD | request | valid acquisition | CAP: REQUIRED | nothing preserved |
| NEX-MET | evidence | any preserved evidence | EVD: REQUIRED | — |
| NEX-IMG | evidence | media_type = IMAGE | EVD: REQUIRED | SKIPPED `NOT_APPLICABLE` |
| NEX-VID | evidence | media_type = VIDEO | EVD: REQUIRED | SKIPPED `NOT_APPLICABLE` |
| NEX-AUD | evidence | AUDIO, or VIDEO with an audio stream | EVD: REQUIRED | SKIPPED `NOT_APPLICABLE` (no audio stream is detected by AUD itself) |
| NEX-PRV | evidence | format supported by the C2PA SDK | EVD: REQUIRED | SKIPPED `NOT_APPLICABLE`; absence of credentials is a result, not a skip |
| NEX-SRC | case | investigator/acquisition supplied a URL | entry not defined in A1 → D-13 | — |
| NEX-FPM | evidence + case | at least one of IMG/VID/AUD COMPLETED for the evidence | MET: OPTIONAL · IMG: CONDITIONAL (IMAGE) · VID: CONDITIONAL (VIDEO) · AUD: CONDITIONAL (has audio) · SRC: OPTIONAL | SKIPPED `UPSTREAM_FAILED` |
| NEX-MOC | case | FPM produced candidates | FPM: REQUIRED · SRC: OPTIONAL | SKIPPED `UPSTREAM_FAILED`; zero candidates = COMPLETED with "no related version in searched scope" |
| NEX-ALN | case (pairs) | MOC proposed ≥1 comparable pair | MOC: REQUIRED · IMG: CONDITIONAL (image pairs) · VID: CONDITIONAL (video pairs) | SKIPPED `NO_INPUT` |
| NEX-TRN | case (pairs) | MOC pair exists | MOC: REQUIRED · ALN: CONDITIONAL (time-based pairs) | SKIPPED `NO_INPUT` |
| NEX-CMC | evidence + case | ≥1 upstream COMPLETED | IMG, VID, AUD, PRV, TRN: all OPTIONAL | SKIPPED `NO_INPUT` |
| NEX-EGC | case | always (records exist) | SRC, MOC, TRN, CMC: all OPTIONAL | — |
| NEX-REC | case | EGC COMPLETED | EGC: REQUIRED | SKIPPED `UPSTREAM_FAILED` |
| NEX-INV | case | human | REC: REQUIRED for case conclusions (finding review earlier, D-15) | conclusions blocked; finding review allowed |
| NEX-RPT | case | human request | INV: OPTIONAL for DRAFT, REQUIRED for FINAL (D-16) | FINAL refused |

Registry properties enforced by tests: (1) the set of solid edges equals A1 exactly, including `SRC → MOC`; (2) the graph is acyclic; (3) every T-MIR-planned module has an applicability rule; (4) failure propagation follows the edge types above; (5) no plan can wait forever — a module whose REQUIRED upstream is terminal and not COMPLETED becomes SKIPPED immediately.

---

## 9. T-MIR execution ownership mapping

| Module | Executed by | Trigger | T-MIR role |
|---|---|---|---|
| NEX-CM | Case Service (API request, transactional) | Investigator | Observes `case.*` events |
| NEX-CAP | Evidence Service acquisition (API request, streaming) | Upload / share / retrieved bytes | Observes |
| NEX-EVD | Evidence Service preservation (API request) | After CAP | Observes `evidence.preserved` → may plan a run (auto-run setting, default ON) |
| NEX-MET, IMG, VID, AUD, PRV | **T-MIR**, per-evidence executions in workers | Run plan | Executes |
| NEX-SRC | Source Service; `SOURCE_RESOLUTION` job in workers | Investigator adds/refreshes a source | Observes `source.*` → re-plans FPM/MOC/EGC |
| NEX-FPM, MOC, ALN, TRN, CMC, EGC, REC | **T-MIR**, case-scope executions in workers | Run plan | Executes |
| NEX-INV | Review Service (API request, human) | Investigator | Observes; unlock signal when REC completes |
| NEX-RPT | Report Service; `REPORT_GENERATION` job | Investigator | Observes; may warn when the report would reference superseded results |

T-MIR responsibilities from the reconciliation prompt, and where each lives: dependency resolution & planning → `Planner` + registry; persistent scheduling, worker coordination, retries, cancellation, timeouts, recovery → Job Service + worker; parallel/sequential execution → planner emits ready sets, worker pool runs them concurrently up to `WORKER_CONCURRENCY` with per-module resource classes (`LIGHT`, `CPU_HEAVY`, `GPU_OPTIONAL`); artifacts → artifact store + `artifact_records`; result persistence → `analysis_results/findings`; progress → per-execution measured progress only; events → outbox; audit → executions + events; re-execution and duplicate prevention → input fingerprints (D-8, D-14).

---

## 10. Frontend route compliance mapping

| Route | Exists | Purpose matches B | Data | Context | Backend APIs exist | States (load/empty/error) | Action |
|---|---|---|---|---|---|---|---|
| `/` | Yes — marketing landing page | **No** (B: redirect) | static | — | n/a | n/a | D-1 |
| `/dashboard` | Yes | Mostly (needs jobs, failed jobs, health, live updates) | mock | defaults to "most urgent case" | cases ✔, evidence stats ✔, health ✔, jobs ✘ | global only | Wire + job panels |
| `/investigations` | Yes (+ `/active`, `/completed`, `/archived`) | Yes; needs last activity, evidence count | mock | n/a | ✔ | partial | Wire |
| `/investigations/new` | Yes | Needs objectives, category | mock | n/a | ✔ (fields missing) | partial | Wire + Phase 04 delta |
| `/investigations/:caseId` | Yes, 8 tabs (overview, evidence, analysis/[branch], timeline, graph, review, report, events) | Yes, richest page; needs module execution overview | mock | URL ✔ | case/evidence/events ✔; rest ✘ | partial | Wire progressively by phase |
| `/evidence` | Yes (+ workbench `/evidence/:id/{analysis,integrity,metadata,preview,timeline}`) | Yes | mock | URL ✔ | upload, metadata, integrity, preview, download, history ✔; analysis ✘ | partial | Wire now (Phase 11 slice) |
| `/sources` | **No** | — | — | — | ✘ | — | Create in Phase 07/10 |
| `/lineage` | **No** | — | — | — | ✘ | — | Create in Phase 07/10 |
| `/intelligence` | **No** | — | — | — | ✘ | — | Create in Phase 05/10 (registry + executions first) |
| `/graph` | Yes | Yes | mock graph | defaults | ✘ | partial | Phase 09 |
| `/reports` | Yes (+ `/:id`, `/:id/preview`) | Yes | mock | from report | ✘ | partial | Phase 09 |
| `/notifications` | Yes | Partly (currently "decisions waiting") | mock | n/a | ✘ | partial | Phase 05/11 (D-21) |
| `/system` | Yes (+ `/health`, `/logs`) | Partly — shows mock audit "signatures verified" (not real) | mock | n/a | health/db/storage ✔; workers/queue/modules ✘ | partial | Wire now; remove fake audit claims |
| `/settings` | Yes | Minimal | localStorage | n/a | ✘ | — | Phase 11 (D-21) |

Global shell: navigation exists (8 items — add Sources, Lineage, Intelligence); search is client-only (→ D-20); job monitor missing; system status indicator missing.

---

## 11. API and database ownership mapping

### 11.1 APIs (all under `/api/v1`; ✔ = exists and tested)

| B domain | Service | Endpoints |
|---|---|---|
| Health APIs | HealthService | ✔ `/health`, ✔ `/health/ready`, ✔ `/system/database`, ✔ `/system/storage`; planned `/system/status`, `/system/workers`, `/system/modules`, `/system/projections`, `/system/config` |
| Case APIs | Case Service (NEX-CM) | ✔ `/cases` (POST, GET), ✔ `/cases/statistics`, ✔ `/cases/{id}` (GET, PATCH), ✔ `/archive`, ✔ `/reopen`, ✔ `/summary`, ✔ `/statistics`, ✔ `/events` |
| Evidence APIs | Evidence Service (NEX-CAP/EVD) | ✔ `POST/GET /cases/{id}/evidence`, ✔ `/evidence/statistics`, ✔ `/evidence/{id}`, ✔ `/metadata`, ✔ `/integrity`, ✔ `/verify-integrity`, ✔ `/preview`, ✔ `/download`, ✔ `/history`; planned `GET /evidence` (global list), `/evidence/{id}/artifacts` |
| Analysis APIs | Analysis Service | planned `POST /evidence/{id}/analyze` (202), `GET /evidence/{id}/analysis`, `GET /analyses/{id}`, `/analyses/{id}/{image,video,audio,provenance}`, `/artifacts`, `/reproducibility`, `POST /analyses/{id}/retry` |
| T-MIR APIs | T-MIR Service | planned `GET /tmir/modules` (registry + availability), `POST /cases/{id}/runs`, `GET /cases/{id}/runs`, `GET /runs/{id}` (plan + executions), `GET /cases/{id}/lineage`, `/lineage/relationships`, `/lineage/compare`, `/alignment`, `/transformations`, `/correlation`, `/reconstruction`, `/timeline` |
| Source APIs | Source Service (NEX-SRC) | planned `POST/GET /cases/{id}/sources`, `GET /sources`, `/sources/{id}`, `/resolve`, `/refresh`, `/history`, `/sources/connectors` |
| Graph APIs | Evidence Graph Service (NEX-EGC) | planned `/cases/{id}/graph`, `/graph/nodes`, `/graph/edges`, `/graph/statistics`, `/graph/nodes/{id}`, `/graph/edges/{id}` |
| Report APIs | Report Service (NEX-RPT) | planned `POST/GET /cases/{id}/reports`, `GET /reports`, `/reports/{id}`, `/preview`, `/download`, `/history` |
| Job APIs | Job Service | planned `GET /jobs`, `/jobs/{id}`, `POST /jobs/{id}/cancel`, `/retry` |
| *Addition* Review APIs | Review Service (NEX-INV) | planned `GET/POST /cases/{id}/review`, `PATCH /reviews/{id}`, `GET/POST /cases/{id}/decisions` |
| *Addition* | Notification / Preferences / Search | planned `/notifications…`, `/preferences`, `/search` |
| Live | Event Publisher | planned `WS /ws/events`, `/ws/jobs/{id}`, `/ws/cases/{id}` |

### 11.2 Database (PostgreSQL authoritative)

| Table | Owner service | Module | Status |
|---|---|---|---|
| `cases` | Case | NEX-CM | ✔ (add objectives, category) |
| `evidence`, `investigation_events` | Evidence / all (audit) | NEX-CAP, NEX-EVD | ✔ |
| `evidence_metadata` | Analysis | NEX-MET | ✔ (becomes MET's specialised output) |
| `analysis_jobs` | **Job** | — | planned (Phase 03) |
| `analysis_executions` | T-MIR | 12 modules | planned (03) |
| `analysis_results`, `analysis_findings` | Analysis | all modules | planned (03) |
| `artifact_records` | Evidence (storage) | all modules | planned (03) |
| `outbox_events`, `projection_checkpoints` | Event Publisher | — | planned (03 / 07) |
| `notifications`, `preferences` | Notification / Settings | — | planned (05 / 11) |
| `source_records`, `source_observations` | Source | NEX-SRC | planned (07) |
| `media_fingerprints` | Analysis | NEX-FPM | planned (07) |
| `media_relationships` | T-MIR (per B) | NEX-MOC | planned (07) |
| `evidence_nodes`, `evidence_edges` | Evidence Graph | NEX-EGC | planned (09) |
| `reviews`, `decisions` | Review | NEX-INV | planned (09) |
| `reports`, `report_versions` | Report | NEX-RPT | planned (09) |
| Object storage `Originals/`, `Derived/`, `Reports/`, `Temporary/` | Evidence (storage adapter) | all | ✔ Originals/Temporary; others planned |
| Neo4j (projection of nodes/edges/relationships) | Graph projection consumer | EGC, MOC | planned (07) |
| Qdrant (projection of embeddings) | Vector projection consumer | FPM | planned (07, only with an adopted embedding model) |

---

## 12. Infrastructure requirements

| Need | Phase | Status / note |
|---|---|---|
| PostgreSQL 17 (Compose) | 02 | ✔ running |
| FFmpeg/FFprobe | 04+ | ✔ 9.1 installed |
| Worker process (`python -m Backend.App.Workers.Worker`) | 05 | new; started alongside the API |
| C2PA Python SDK (`c2pa-python`) | 06 | install + licence check |
| PyTorch + selected detectors (CPU first; RTX 5050 needs CUDA 12.8+ wheels if GPU used) | 06 | comparison before adoption |
| Chromaprint (`fpcalc`) or alternative audio fingerprint | 07 | suitability test for short speech clips |
| ImageHash or equivalent perceptual hashing | 07 | licence check |
| Neo4j 5 Community, Qdrant (Compose) | 07 | ~2–3 GB RAM together; fits 23 GB |
| PDF renderer (ReportLab preferred over WeasyPrint on Windows) | 09 | licence check |
| Node deps installed in `Frontend/Web`, pinned | 10 | not installed yet |
| Playwright (Node) for E2E | 10–13 | not installed |
| CI (GitHub Actions with a PostgreSQL service) | 12 | current workflow runs no tests |

---

## 13. Proposed implementation order

1. **Phase 01 completion (after approval):** write the architecture documents (§15) with both module flowcharts and Flowchart B stored verbatim; commit point suggested.
2. **Phase 03:** contract types, dependency registry + tests, migration `0003` (jobs, executions, results, findings, artifacts, outbox), Phase 04 delta fields.
3. **Phase 05:** Job Service, worker, planner, outbox dispatcher, WebSocket gateway, notifications consumer; move NEX-MET into T-MIR; Job / Analysis / T-MIR APIs; `/system/workers`, `/system/modules`.
4. **Phase 10/11 first slice (recommended here, not at the end):** with Raghav — real API adapter, explicit case context, dashboard / investigations / new / workspace / evidence on real data, job monitor and system status on real endpoints, `/intelligence` showing the registry and live executions. This puts a working vertical demo in place early.
5. **Phase 06** media engines (each lands with its Intelligence panel).
6. **Phase 07** SRC / FPM / MOC + Neo4j / Qdrant, with `/sources` and `/lineage`.
7. **Phase 08** ALN / TRN / CMC on a small controlled dataset.
8. **Phase 09** EGC / REC / INV / RPT with graph, review and report pages.
9. **Phase 11** remainder (search, notifications, settings), **Phase 12** hardening, **Phase 13** UI/UX audit.

---

## 14. Risks and blockers

| Risk | Impact | Mitigation |
|---|---|---|
| Frontend ownership: most frontend changes touch Raghav's code; the contract replacement is invasive. | Merge conflicts, duplicated effort | Agree D-1, D-18, D-19 with Raghav before Phase 10/11; backend publishes OpenAPI first. |
| No approved deepfake detectors; GPU support for RTX 5050 (sm_120) needs recent PyTorch builds. | Core "AI-powered" requirement | Phase 06 comparison on CPU first; record licence, accuracy source, latency. |
| No controlled ground-truth dataset (NEXTRON-MV) exists. | Phases 07–08 cannot be validated | Build a small consented set (FFmpeg-derived variants) during Phase 06. |
| Social platform connectors need credentials and policy approval. | SRC limited to generic public URLs | Ship generic connector + honest "restricted/unsupported" states. |
| Deadline and judging criteria unknown. | Scope pressure | Phase order puts a working vertical slice early. |
| Frontend deps unpinned (`latest`) and not installed; folder casing `frontend` vs `Frontend`. | Non-reproducible builds, tooling breakage | Pin from lockfile; Git-aware case rename agreed with Raghav. |
| Large uncommitted backend change set. | Loss or conflicts with teammates | Commit Steps 0–2 before Phase 03 (on your instruction). |
| Pillow decodes in-process; Neo4j/Qdrant add operational load. | Parser exploits; resource use | Phase 12 isolation; projections only when needed (D-12). |

---

## 15. Expected files and directories affected

**Phase 01 (documents only)** — `Documentation/Architecture/`: `Module Connectivity.md` (A1 then A2, verbatim), `Application Architecture.md` (B verbatim), `Module Contracts.md`, `Orchestration.md`, `API Contracts.md`, `Data Architecture.md`, `Architectural Decisions.md`; `Documentation/Implementation/`: `Repository Audit.md`, `Implementation Plan.md` (this file, once approved), `Architecture Compliance.md`, `Implementation Status.md`; `Documentation/Testing/`: `Test Plan.md`, `Validation Report.md`.

**Phase 03** — `Backend/App/Contracts/` (`ModuleResult.py`, `Findings.py`, `Artifacts.py`, `ExecutionStates.py`), `Backend/App/Orchestration/TMir/DependencyRegistry.py`, `Database/PostgreSQL/Models/{AnalysisJob,AnalysisExecution,AnalysisResult,AnalysisFinding,ArtifactRecord,OutboxEvent}.py`, migration `0003`, tests.

**Phase 05** — `Backend/App/Orchestration/TMir/{Planner,ExecutionContext,ModuleExecutor,Service}.py`, `Backend/App/Workers/{Worker,JobService,OutboxDispatcher}.py`, `Backend/App/Realtime/{WebSocketRouter,ConnectionManager}.py`, `Backend/App/Api/V1/{Jobs,Analysis,TMir,Notifications}.py`, `Backend/App/Modules/NexMet/*` (re-homed), `Backend/App/Modules/NexCap/Service.py` (stop inline extraction).

**Phases 06–09** — `Backend/App/Modules/Nex{Img,Vid,Aud,Prv,Src,Fpm,Moc,Aln,Trn,Cmc,Egc,Rec,Inv,Rpt}/`, `Database/Neo4j/`, `Database/Qdrant/`, `Infrastructure/Docker/docker-compose.yml` (two services), `Scripts/Maintenance/Rebuild*.py`, `Datasets/NEXTRON-MV/` manifests.

**Phases 10–13** — `Frontend/Web/src/api/*` (contract + adapter), `stores/`, `layouts/` (job monitor, status), `config/navigation.ts`, `app/(workspace)/{sources,lineage,intelligence}/`, module screens; `Tests/End-To-End/` (Playwright); `.github/workflows/*`; `Infrastructure/Docker/*.Dockerfile`.

---

## 16. Verification strategy per phase

| Phase | Done only when |
|---|---|
| 01 | Flowcharts in the documents are byte-identical to the supplied text (scripted diff); every conflict in §3 is recorded with a decision or an open question. |
| 03 | Registry test proves edge set = A1, acyclic, every module typed; migration `0003` upgrades and downgrades on a clean database; `alembic check` clean; contract round-trip tests (Pydantic ↔ JSON schema). |
| 04 delta | New case fields persist, validate and appear in list/detail; existing 84 tests still pass. |
| 05 | `POST /evidence/{id}/analyze` returns 202 with a job committed before the response; the separate worker claims it (two workers never claim the same job); MET runs inside T-MIR; WebSocket client receives events in order and resumes after reconnect with no gaps; killing the worker mid-run → lease expiry → another worker completes without duplicate results; cancel and timeout tested; image-only evidence ends with AUD/VID SKIPPED `NOT_APPLICABLE`, never waiting. |
| 06 | Each engine returns real results on fixtures, or UNAVAILABLE when its tool/model is absent; detector comparison document with sources, licences and measured CPU latency; no confidence without a documented basis. |
| 07 | SSRF tests (private IPs, redirects, DNS rebinding) refuse; perceptual/audio fingerprints rank derived variants above unrelated media on the controlled set (precision/recall reported); Neo4j/Qdrant projections rebuild from PostgreSQL to identical counts; outage → lag visible → catch-up. |
| 08 | Known offsets/trims/splices recovered within stated tolerance (temporal IoU, boundary error reported); unknown cases remain INCONCLUSIVE. |
| 09 | Every graph edge links to stored findings; reviews versioned and separate from machine findings; report JSON/PDF hashes recorded; regenerated report preserves the old version; FINAL refused without required review. |
| 10–11 | Playwright: every route loads on real data, deep links and refresh work, back/forward work, loading/empty/error/offline states render, upload → analysis → live progress → findings end-to-end, backend stopped → honest error, reconnect → reconciled state; no console errors. |
| 12 | Security suite (upload, SSRF, path traversal, oversized input), reliability suite (worker crash, DB down, storage down), performance baseline with hardware recorded, backup → restore drill, CI green on a clean runner. |
| 13 | Screenshot audit of every page at desktop and mobile widths with findings list; fixes verified by re-running the Playwright suite. |

---

## 17. Decisions needed from you before Phase 01 continues

1. **D-1 — `/` route:** redirect to `/dashboard` and move the landing page to `/about` (default), or keep the landing page at `/`?
2. **C-1 / D-2 — T-MIR boundary:** approve "T-MIR executes the 12 A1 modules and observes the other six"?
3. **C-4 — audio alignment:** accept the limitation (ALN gets audio only via MOC/FPM), or do you want `AUD → ALN` added to the canonical flowchart?
4. **Frontend work:** should I change `Frontend/Web` myself in Phases 10–11, or prepare the backend contract and hand the frontend changes to Raghav?
5. **Approval** of the phase order in §13 (frontend slice right after Phase 05).
