# Implementation Status

## Local visual search addition (26 November 2026)

**IMPLEMENTED AND VERIFIED:** SigLIP 2 Base/16 embeddings are stored in PostgreSQL and indexed in Qdrant by the worker. `/sources` accepts an image, screenshot, or safely fetched image URL with an optional crop. The API filters Qdrant by investigation and validates returned evidence IDs in PostgreSQL. A live self-match returned cosine 1.0. The opt-in SerpApi Google Lens search passed provider-contract tests and live requests with a generated image; the Free Plan check succeeded and five unverified web leads were returned per request. Bounded server-fetched previews work when the source permits retrieval, with a source-link fallback when it does not. No private evidence was sent in the verification requests. See [Visual Search](../Research/Visual%20Search.md) for setup, references, and limits.

As of 26 November 2026, during Step 5. Categories: IMPLEMENTED AND VERIFIED · IMPLEMENTED BUT NOT VERIFIED ·
PARTIALLY IMPLEMENTED · NOT IMPLEMENTED · BLOCKED · NOT APPLICABLE. "Verified" means an automated test or a
recorded manual check ran against the real stack (see [Validation Report](../Testing/Validation%20Report.md)).

## Modules

| Module | Status | Evidence |
|---|---|---|
| NEX-CM Case Management | IMPLEMENTED AND VERIFIED | API tests, Playwright lifecycle test |
| NEX-CAP Evidence Acquisition | IMPLEMENTED AND VERIFIED | Upload, validation and size-limit tests; Playwright upload |
| NEX-EVD Evidence Preservation | IMPLEMENTED AND VERIFIED | Hash, integrity, tamper, restart and immutability tests |
| NEX-MET Metadata Intelligence | PARTIALLY IMPLEMENTED | FFprobe/Pillow extraction verified; runs in T-MIR workers with a result envelope and an OBSERVATION finding; no XMP or inconsistency analysis |
| NEX-IMG Image Forensics | PARTIALLY IMPLEMENTED | ELA, block noise consistency, resampling traces, JPEG quantisation, perceptual hashes, heatmaps; verified on genuine / spliced / recompressed / resized fixtures. **No evaluated synthetic-image detector** (results end PARTIALLY_COMPLETED / DETECTOR_NOT_INSTALLED) |
| NEX-VID Video Forensics | PARTIALLY IMPLEMENTED | Packet timing (gaps, VFR, keyframes), abrupt visual changes at exact timestamps, frame signatures, contact sheet; verified on a hard cut and a timestamp gap. **No evaluated video deepfake detector** |
| NEX-AUD Audio Forensics | PARTIALLY IMPLEMENTED | Levels, digital silence, bandwidth, spectral discontinuities, spectrogram, 16 kHz working copy; reports a missing audio stream itself. Chromaprint only when `fpcalc` is installed (not installed here). **No evaluated synthetic-speech detector** |
| NEX-PRV Provenance Intelligence | IMPLEMENTED AND VERIFIED | C2PA SDK: absent / valid-untrusted / invalid (tampered) / unsupported verified with generated signed fixtures. No trust list configured; remote manifests not fetched |
| NEX-SRC Source Intelligence | PARTIALLY IMPLEMENTED | Generic connector, SSRF-safe retrieval (47 tests), retrieval history, media preserved as evidence; platform connectors need approved APIs |
| NEX-FPM Fingerprint & Similarity | IMPLEMENTED AND VERIFIED | Image/frame/audio fingerprints; controlled set precision 1.00, recall 0.91; image-to-frame matching |
| NEX-MOC Media Lineage | PARTIALLY IMPLEMENTED | Candidate relationships, ordering by claimed publication times; relationships stay CANDIDATE (reviews are separate records) |
| NEX-ALN Temporal Alignment | PARTIALLY IMPLEMENTED | Video offset/speed (±0.5 s) and audio offset (±0.05 s) recovered on ground truth; one execution per case covers all pairs |
| NEX-TRN Transformation Analysis | PARTIALLY IMPLEMENTED | Trim, speed, audio replacement, resize, crop/reframe, re-encode hypotheses; trim and audio replacement verified |
| NEX-CMC Cross-Modal Correlation | PARTIALLY IMPLEMENTED | Coincident picture/sound discontinuities verified on a splice; provenance/image/detector agreement and disagreement rules |
| NEX-EGC Evidence Graph Construction | IMPLEMENTED AND VERIFIED | Append-only snapshot per run from PostgreSQL records (case, evidence, sources, candidate versions, findings, citations); every edge names its supporting record; projected to Neo4j |
| NEX-REC Timeline & Reconstruction | PARTIALLY IMPLEMENTED | Dated statements labelled by who states them (file, source, NEXTRON); TIME_CONFLICT when a file claims creation after its source's stated publication, verified; no event-level reconstruction beyond that |
| NEX-INV Review & Decision | IMPLEMENTED AND VERIFIED | Accept / reject / inconclusive / needs more evidence with rationale on findings, relationships and the case conclusion; append-only versions (database trigger); a conclusion needs a completed reconstruction. Single local operator: no reviewer roles |
| NEX-RPT Reporting | IMPLEMENTED AND VERIFIED | REPORT_GENERATION jobs write write-once JSON and PDF (ReportLab) with SHA-256; DRAFT any time, FINAL only after a reviewed conclusion; download checked against the recorded hash |
| Pretrained detectors in an isolated host process (pinned weights, restricted loading, timeouts, restart) | IMPLEMENTED AND VERIFIED | Benchmarked locally ([Detector Benchmark](../Testing/Detector%20Benchmark.md)); host tests on the real models (hang, crash, unknown detector) |
| Derived artifacts (heatmaps, frame sets, signatures, audio tracks) | IMPLEMENTED AND VERIFIED | Write-once read-only files under `Derived/`, SHA-256 recorded, served inert by `GET /artifacts/{id}` |
| T-MIR: dependency registry and decisions | IMPLEMENTED AND VERIFIED | Registry tests incl. flowchart parse and 900-run deadlock simulation |
| T-MIR: planner, runner, executors, result envelopes | IMPLEMENTED AND VERIFIED | Image/video/audio plan tests; every entry ends with one envelope; reuse by input fingerprint |
| T-MIR: per-pair expansion of NEX-ALN / NEX-TRN | NOT IMPLEMENTED | One `<case>:pairs` placeholder, skipped NO_INPUT until NEX-MOC proposes pairs (Step 6) |
| Job Service and worker process (leases, heartbeats, recovery, retry with backoff, cancel, module and job timeouts) | IMPLEMENTED AND VERIFIED | Concurrency, fencing, crash-recovery, timeout and real-subprocess tests |
| Module contracts (results, findings, artifacts, states) | IMPLEMENTED AND VERIFIED | Contract tests; database constraint tests |

## Routes (Flowchart B)

| Route | Status |
|---|---|
| `/` (landing page), `/dashboard`, `/investigations` (+ filters), `/investigations/new`, `/investigations/:caseId` (overview, evidence, add, analysis: All, Image, Video, Audio, Provenance; timeline, events), `/evidence` (+ every item tool incl. analysis), `/sources`, `/lineage`, `/intelligence`, `/notifications`, `/system` (+ health, workers), `/settings`, job monitor | IMPLEMENTED AND VERIFIED (Playwright) |
| `/graph`, `/reports`, case graph/review/report tabs, reconstruction on the case timeline | IMPLEMENTED AND VERIFIED (Playwright) |
| `/system/logs` | PARTIALLY IMPLEMENTED: page exists and states that its backend is not built; no data |
| `/about` | IMPLEMENTED AND VERIFIED (same landing page as `/`) |

## Infrastructure and data

| Item | Status |
|---|---|
| PostgreSQL 17.12 (Compose, 127.0.0.1:5433), migrations 0001–0007 | IMPLEMENTED AND VERIFIED |
| Protected evidence storage, reconciliation script | IMPLEMENTED AND VERIFIED |
| Transactional outbox, gap-safe dispatcher, WebSocket `/ws/events`, `/ws/jobs/{id}`, `/ws/cases/{id}` (replay then live) | IMPLEMENTED AND VERIFIED |
| Notifications derived from outbox events (runs, integrity, failed source retrievals, reports), filtered by the operator's preferences; reading publishes `notification.read` so other tabs refresh | IMPLEMENTED AND VERIFIED |
| Global search (`/search`, Ctrl K): investigations, evidence, sources, current findings, reports, reviews; LIKE wildcards matched literally | IMPLEMENTED AND VERIFIED |
| Operator preferences (`/preferences`, migration 0009): notification kinds, automatic analysis, default report download; versioned, stale saves refused (409), `preferences.updated` keeps tabs in step | IMPLEMENTED AND VERIFIED (API tests; two-tab Playwright test) |
| `/system/config`: non-secret configuration (no credentials, database address or paths) | IMPLEMENTED AND VERIFIED |
| Live-update recovery: resume with `?after=<last>`, immediate retry on `online` / tab shown, full refetch if the event history restarted, "Reconnecting" status chip and banner | IMPLEMENTED AND VERIFIED (dropped-connection Playwright test) |
| Neo4j 5.26 Community (Compose, 127.0.0.1:7687/7474, pinned by digest), graph projection | IMPLEMENTED AND VERIFIED: the worker projects each case's latest snapshot from the outbox (gap-safe checkpoint `neo4j`), `GET /system/projections` reports checkpoint, lag and counts, `POST /system/projections/neo4j/rebuild` re-projects from PostgreSQL |
| Qdrant | DEFERRED by the data architecture: added once an embedding model is adopted; perceptual hashes stay in PostgreSQL |
| Authentication | NOT APPLICABLE for now: single local operator by design; required before any external deployment |
| Dockerfiles (backend: API, worker, tests; frontend: standalone Next.js), Compose profiles `app` and `ci` | IMPLEMENTED AND VERIFIED: images built; backend suite green in the clean image; containerised stack smoke-tested (upload → run → report; production web under CSP) |
| CI (`.github/workflows/ci.yml`: backend + audit, frontend typecheck/build/audit, Playwright, image builds) | WRITTEN, NOT YET RUN (runs on GitHub when pushed) |
| Security hardening: Origin guard, security headers, CSP, rate limit, production guard | IMPLEMENTED AND VERIFIED ([Security Review](../Testing/Security%20Review.md)); authentication still NOT IMPLEMENTED |
| Encrypted backup, verified restore, outage drill | IMPLEMENTED AND VERIFIED ([Backup and Recovery](../Operations/Backup%20and%20Recovery.md)) |
