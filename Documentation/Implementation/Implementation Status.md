# Implementation Status

As of 26 November 2026, after Step 4. Categories: IMPLEMENTED AND VERIFIED · IMPLEMENTED BUT NOT VERIFIED ·
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
| NEX-SRC … NEX-RPT (10 modules) | NOT IMPLEMENTED | T-MIR plans them and records UNAVAILABLE / MODULE_NOT_IMPLEMENTED (or SKIPPED with a reason) on every run |
| Derived artifacts (heatmaps, frame sets, signatures, audio tracks) | IMPLEMENTED AND VERIFIED | Write-once read-only files under `Derived/`, SHA-256 recorded, served inert by `GET /artifacts/{id}` |
| T-MIR: dependency registry and decisions | IMPLEMENTED AND VERIFIED | Registry tests incl. flowchart parse and 900-run deadlock simulation |
| T-MIR: planner, runner, executors, result envelopes | IMPLEMENTED AND VERIFIED | Image/video/audio plan tests; every entry ends with one envelope; reuse by input fingerprint |
| T-MIR: per-pair expansion of NEX-ALN / NEX-TRN | NOT IMPLEMENTED | One `<case>:pairs` placeholder, skipped NO_INPUT until NEX-MOC proposes pairs (Step 6) |
| Job Service and worker process (leases, heartbeats, recovery, retry with backoff, cancel, module and job timeouts) | IMPLEMENTED AND VERIFIED | Concurrency, fencing, crash-recovery, timeout and real-subprocess tests |
| Module contracts (results, findings, artifacts, states) | IMPLEMENTED AND VERIFIED | Contract tests; database constraint tests |

## Routes (Flowchart B)

| Route | Status |
|---|---|
| `/` (landing page), `/dashboard`, `/investigations` (+ filters), `/investigations/new`, `/investigations/:caseId` (overview, evidence, add, analysis: All, Image, Video, Audio, Provenance; timeline, events), `/evidence` (+ every item tool incl. analysis), `/intelligence`, `/notifications`, `/system` (+ health, workers), `/settings`, job monitor | IMPLEMENTED AND VERIFIED (Playwright) |
| `/sources`, `/lineage`, `/graph`, `/reports`, `/system/logs`, case graph/review/report tabs | PARTIALLY IMPLEMENTED: page exists and states that its backend is not built; no data |
| `/about` | IMPLEMENTED AND VERIFIED (same landing page as `/`) |

## Infrastructure and data

| Item | Status |
|---|---|
| PostgreSQL 17.12 (Compose, 127.0.0.1:5433), migrations 0001–0005 | IMPLEMENTED AND VERIFIED |
| Protected evidence storage, reconciliation script | IMPLEMENTED AND VERIFIED |
| Transactional outbox, gap-safe dispatcher, WebSocket `/ws/events`, `/ws/jobs/{id}`, `/ws/cases/{id}` (replay then live) | IMPLEMENTED AND VERIFIED |
| Notifications derived from outbox events | IMPLEMENTED AND VERIFIED |
| Neo4j, Qdrant | NOT IMPLEMENTED (Step 5) |
| Authentication | NOT APPLICABLE for now: single local operator by design; required before any external deployment |
| CI, Dockerfiles | NOT IMPLEMENTED (stale files exist; Step 9) |
