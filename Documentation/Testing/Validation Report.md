# Validation Report

Results of test runs that actually executed. Machine: Windows 11, Ryzen 7 260, 23 GB RAM; Python 3.11.9;
PostgreSQL 17.12 (Docker); Node 24.22; Next.js 16.4.6; Playwright 1.65.1 (Chromium).

## Step 4 — 26 November 2026

| Check | Command | Result |
|---|---|---|
| Backend tests | `python -m pytest Tests` | **175 passed** (warnings: Starlette's httpx deprecation; Pillow's decompression-bomb warning in the test that proves the bomb is refused) |
| Models match migrations | `alembic check` | No new upgrade operations (Step 4 needed no migration) |
| Frontend typecheck and production build | `npx tsc --noEmit`, `npx next build` | exit 0 |
| End-to-end, real stack (API + worker + frontend) | `npx playwright test` | **13 passed** |

Engine tests (`Integration/Engines/test_engines.py`, 18), each on a fixture whose answer is known by construction:

| Engine | Fixture → expected and observed |
|---|---|
| NEX-IMG | Genuine JPEG → no localised response, IJG quality 92 recovered · Pasted clean block → noise inconsistency region covering the paste (x 40–65 %, y 33–60 %), not the whole image · Benign recompression at q 70 → no false region, quality 70 · 1.5× resize → interpolation trace at 1/3 cycle/px; original → none · Same input twice → identical findings and artifact bytes · 90 MP image → refused before decoding |
| NEX-VID | Hard cut at 2.0 s → discontinuity ending at 2.0 s (±0.25 s sampling), 25 fps, no gaps · Frames 1.5–3.5 s removed → one timestamp gap at 1.48 s of 2.04 s · Frame/time mapping identical across runs |
| NEX-AUD | Digital silence at 1.0–1.2 s and a replaced segment from 2.5 s → both located · Continuous recording → no candidates · 8 kHz audio upsampled to 44.1 kHz → 99 % bandwidth ≤ 4 kHz versus > 4 kHz for full-band · Video without audio → SKIPPED / NOT_APPLICABLE reported by the module · Missing `fpcalc` → stated as a limitation |
| NEX-PRV | No manifest → ABSENT, with "not evidence of manipulation" · Signed with a generated certificate → VALID, signer named, `signingCredential.untrusted` · Bytes changed after signing → INVALID, `assertion.dataHash.mismatch` · Ogg → SKIPPED / NOT_APPLICABLE |

API test: a run on an MP4 stores the contact sheet, frame signatures, spectrogram and audio track as read-only files;
the envelope lists them; `GET /artifacts/{id}` returns bytes whose SHA-256 equals the record and the header.
End-to-end (`Specs/step4-engines.spec.ts`): an uploaded JPEG with a pasted block is analysed by the real worker; the
Analysis tab shows the noise finding with the region marked on the image and its heatmap loaded from the artifact
API; provenance shows no credentials; the case's Image and Provenance tabs show the results; Video has nothing.

Found and fixed during Step 4:
- The first resampling method (peaks in the 2-D residual spectrum) did **not** detect resizing on the fixtures; it was
  replaced by second-derivative periodicity (Gallagher; Mahdian & Saic), which separates 1.25×–1.6× resizes (robust z
  114–245) from originals (z ≤ 7). Exact 2× is not reliably detected and the finding says so.
- NEX-AUD flagged the AAC encoder's start-up transient as an edit; the first and last 0.25 s are no longer searched.
- The STFT originally held every frame in memory (≈ 460 MB for 10 min at 48 kHz); it now runs in chunks.

What Step 4 does **not** provide: an evaluated deepfake / synthetic-media detector for any modality. The archive
requires comparing candidate models (accuracy, CPU latency, licence, checkpoint provenance) before choosing; that needs
model weights to be downloaded, which was not done without approval. Every image, video and audio result therefore
ends PARTIALLY_COMPLETED / DETECTOR_NOT_INSTALLED and says so. Methods are verified on synthetic fixtures, not on a
labelled real-world benchmark.

## Step 3 — 26 November 2026

| Check | Command | Result |
|---|---|---|
| Backend tests | `python -m pytest Tests` | **154 passed** (1 warning: Starlette's httpx deprecation) |
| Migration 0005 | `alembic upgrade head`, `alembic check` | Applied to the dev database; no new upgrade operations detected; up/down walk tested on a new database |
| Frontend typecheck | `npx tsc --noEmit` (+ a strict unused-code pass over changed files) | exit 0 |
| Frontend production build | `npx next build` | exit 0 |
| End-to-end, real stack (API + one worker process + frontend) | `npx playwright test` | **12 passed** |

New backend tests (`Integration/Orchestration/test_tmir.py`, 20, each on its own freshly migrated database):

| What | How it is checked |
|---|---|
| Image-only run explains every module | All 12 entries end: MET COMPLETED; IMG, PRV, EGC UNAVAILABLE (not built); VID, AUD SKIPPED NOT_APPLICABLE; FPM, MOC, ALN, TRN, CMC, REC SKIPPED NO_INPUT; nothing waits. 12 envelopes, each a valid `ModuleResult` |
| Video and audio plans | Video plans VID and AUD; audio skips VID |
| 202 and reuse | `POST /evidence/{id}/analyze` → 202; the second run reuses MET's result: one COMPLETED execution, one metadata version |
| Concurrent claims | 8 threads claim 30 jobs with `SKIP LOCKED`: 30 distinct claims, none twice |
| Lease fencing | After recovery hands the job to worker B, worker A's heartbeat and finish are refused |
| Worker dies mid-module | Simulated crash before the completing commit: execution left RUNNING, no metadata written; after lease expiry the next worker records attempt 1 FAILED / LEASE_EXPIRED and completes attempt 2; exactly one metadata version, 13 executions = 13 envelopes |
| Crash after a module committed | MET is not re-run; only the interrupted module gets a second attempt |
| Duplicate guard | The database refuses a second COMPLETED execution with the same fingerprint |
| Cancel | Queued → CANCELLED at once; running → flagged, then every remaining entry CANCELLED; terminal → 409 |
| Retry and backoff | Infrastructure error → requeued, then FAILED at `max_attempts`; backoff 10 s × 2^(attempt−1) measured in the database; not claimable early |
| Module timeout | A 3 s module under a 0.5 s limit fails with TIMEOUT; its abandoned run writes nothing |
| Job time limit | Remaining entries CANCELLED / JOB_TIMEOUT, job FAILED with TIMEOUT |
| Outbox | Domain and run events in commit order, 13 module events for a 12-entry run |
| WebSocket | Replay then live, no duplicates; resume with `?after=`; live-only start; foreign Origin refused (1008) |
| Notifications | One per event even when processed twice; read, read-all, 404 |
| Workers | `/system/workers` reflects registration and stop |
| Real worker process | `python -m Backend.App.Workers.Worker` as a subprocess finishes a queued audio run, then is hard-killed (process tree) |

New end-to-end tests (`Specs/step3-tmir.spec.ts`): upload → the queued job runs in the real worker → the Analysis tab
shows each module's state through live events with no reload → findings → a second run reuses NEX-MET's result →
the result envelope opens from the case plan → the notification appears → `/system` shows the heartbeating worker
and a connected live stream; retry from the job monitor queues a new job that the worker finishes.

Failures found and fixed during Step 3:

- **Uploader dropped chosen files on a fresh page load (a Step 1 bug).** `add()` passed the live `FileList` to a
  deferred React state updater and the input was cleared straight after, so whenever React deferred the update the
  list was empty. Found by the new E2E test (direct load of the Add evidence page); fixed by copying the files first.
- **WebSocket "from now" delivered events from before the start.** Without `after` the stream now starts at the
  dispatcher's gap-safe position and skips anything at or below it; a test covers it.
- Findings lookup used SQLAlchemy's generic `ARRAY`, which has no `@>`; the model now uses PostgreSQL's `ARRAY`
  (same `uuid[]` column, no migration).

What the Step 3 checks do **not** cover:
- The worker is killed only in a simulated way mid-module (an exception that nothing catches, then a forced lease
  expiry). The real-process test hard-kills a worker only after its job finished, because NEX-MET finishes in
  milliseconds. A real mid-module kill will be exercised with the slower Step 4 engines.
- Several API processes, and several workers sharing one queue, are tested only through concurrent claims in threads.

## Step 2 — 26 November 2026

| Check | Command | Result |
|---|---|---|
| Backend tests | `python -m pytest Tests` | **134 passed** (1 warning: Starlette's httpx deprecation) |
| Migration on an empty database | `alembic upgrade head` on a new database, then `alembic downgrade base` | 0001 → 0002 → 0003 → 0004 and back to base; only `alembic_version` remains |
| Models match migrations | `alembic check` | No new upgrade operations detected |
| Frontend typecheck | `npx tsc --noEmit` | exit 0 |
| End-to-end | `npx playwright test` | **9 passed** |
| API serves the registry | `GET /system/modules` | 31 edges: 12 REQUIRED, 6 CONDITIONAL, 13 OPTIONAL |

Backend tests by file:

| File | Tests |
|---|---:|
| Unit/Backend/test_acquisition_units.py | 26 |
| Unit/Backend/test_contracts.py | 22 |
| Unit/Backend/test_dependency_registry.py | 16 |
| Unit/Backend/test_envelope.py | 8 |
| Unit/Backend/test_module_catalog.py | 3 |
| Integration/API/test_cases.py | 18 |
| Integration/API/test_evidence.py | 19 |
| Integration/API/test_frontend_support.py | 4 |
| Integration/API/test_health.py | 11 |
| Integration/PostgreSQL/test_analysis_schema.py | 5 |
| Integration/PostgreSQL/test_migrations.py | 2 |
| **Total** | **134** |

Failure found and fixed during Step 2: `outbox_events.schema_version` had only a Python-side default, so a direct
SQL insert failed; it now has a database default (migration 0004 corrected before any data used it).

What the Step 2 checks do **not** cover: nothing writes jobs, executions, results or findings yet (Step 3), so the
contracts are verified by unit tests and database constraint tests, not by a real module run.

## Step 1 — 26 November 2026

| Check | Result |
|---|---|
| Backend tests | 91 passed |
| Frontend production build and typecheck (incl. a strict pass over new code) | Passed |
| Playwright | 9 passed after fixes (unknown analysis types and malformed IDs now real 404s; workspace column overflow) |
| Manual browser check | Create case → upload PNG → server SHA-256 equals browser SHA-256 → metadata → integrity MATCH → custody record |

Screenshots: `Tests/Test Reports/End-To-End/Screenshots/` (18 states, regenerated by each Playwright run).
