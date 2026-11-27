# Validation Report

Results of test runs that actually executed. Machine: Windows 11, Ryzen 7 260, 23 GB RAM; Python 3.11.9;
PostgreSQL 17.12 (Docker); Node 24.22; Next.js 16.4.6; Playwright 1.65.1 (Chromium).

## Experience transformation and Universal Forensic Evidence Viewer — 27 November 2026

| Check | Actual result |
|---|---|
| Backend suite | **276 passed** (adds result supersession, workspace summaries, test-record filter) |
| Playwright, isolated stack (`Scripts/Testing/StartE2EStack.ps1`: database `nextron_e2e`, API :8002, web :8090) | **23 of 23**: 20 in the full run, then the 3 that failed for test reasons (hydration wait, a [E2E] title now hidden by default, one unnamed link) passed after fixes |
| UI audit (`step10-audit.spec.ts`), 32 routes × 1440 and 390 px | **0 hard findings** after the redesign |
| Viewer on real data | Spliced photo: choosing the noise finding focused its recorded region, overlaid the method's own NOISE heatmap and showed the limitation that flat areas such as sky have less noise |

Fixed along the way:
- **Results were never superseded** (since Step 3): re-runs left earlier results current and findings repeated (30 listed, 18 distinct on one photo). Recording now supersedes, and migration 0010 applied the rule to history after an encrypted backup; nothing was deleted.
- **Browser tests wrote into the operator's database.** They now run on an isolated stack with their own database, storage and Qdrant collection.
- 284 of 288 dev investigations are test records; lists hide `[E2E]`/`[Bench]`/`[Drill]`/`[Test]`/`[Smoke]` titles by default, always with the count and a one-click "Show". Nothing was changed or deleted.

Screenshots: before in `Tests/Test Reports/End-To-End/Before Transformation/`, after in `Tests/Test Reports/End-To-End/UI Audit/` (64 each).

Not done: colour-contrast measurement, a screen-reader walkthrough, face-level video localisation (no face detector installed), a pixel-localisation model (TruFor, gap 7), shared-element route transitions.

## Visual search with real photographs — 27 November 2026

Five real camera photographs (RAISE, from the Community Forensics evaluation set already on disk, label "real"). Case
CASE-0269 holds the original and three other real photos; manipulated copies of the original are the queries. Local
search only (nothing sent to the web).

| Query (made from the original) | Rank of original | Cosine, original | Best other photo |
|---|---|---|---|
| Exact re-upload, JPEG 90 | 1 | 0.9998 | 0.8031 |
| Re-compressed JPEG q=35, resized to 40 % | 1 | 0.9340 | 0.7493 |
| Cropped to the central 50 % | 1 | 0.9315 | 0.8399 |
| Mirrored | 1 | 0.9945 | 0.8051 |
| Colour/contrast edited, rotated 4° | 1 | 0.9403 | 0.7712 |
| Spliced (part of another photo pasted in) | 1 | 0.8709 | 0.7265 |
| Social-media-style screenshot | 1 | 0.8854 | 0.7208 |
| **Negative:** unrelated real photo, not in the case | — | 0.6876 | **0.8016** (top result) |

In the browser (Sources page, 50 % crop at JPEG 0.6): original 0.924, its re-compressed copy 0.889, then an
**unrelated** photo 0.829 above the **spliced derivative** 0.827.

What this shows: the original was found first for every manipulation. Search always returns its nearest images, and
unrelated real photos reach 0.80–0.84, so a top result is a lead only when it clearly beats the rest. Scores are
uncalibrated cosine values.

Same copies uploaded as evidence: NEX-MOC linked both to the original as candidates (NEAR_DUPLICATE, pHash distance 0
for the re-compressed copy; SAME_CONTENT_VARIANT, 0.91 for the spliced one), with no claim of direction. NEX-TRN
reported "Resized". **The splice was not detected:** the noise-level region covers the top 36–42 % of the frame on the
untouched original too (scene content), not the pasted area (x 37–63 %, y 34–66 %); error-level analysis flagged a small
area of the re-compressed copy that was not edited; the synthetic-image detector scored both low, correctly, because
nothing was AI-generated. A manipulation-localisation model (TruFor, gap 7) is what this needs.

## Step 10: UI/UX refinement — 27 November 2026

| Check | Actual result |
|---|---|
| Backend suite | **275 passed** in 196 s |
| Playwright | **22 passed** in 3.7 min, including the audit |
| `step10-audit.spec.ts` | 32 routes (every page, case tab and evidence tool) × desktop 1440×900 and phone 390×844, full-page screenshots in `Tests/Test Reports/End-To-End/UI Audit/`. Final run: **0 findings** |

Found by the audit's measurements, all fixed:
- No `h1` on the investigation overview and the evidence overview (both widths): added a page heading for assistive
  technology.
- Phone overflow: the investigation status tabs (401 px in 390 px) now scroll within themselves; the evidence page's
  definition lists (393 px) now wrap.
- Phone tap targets under 24 px: standalone text links (17–21 px) given a 24 px hit area without moving text; search
  inputs, segmented tabs and section links raised; checkboxes 13 → 18 px (and measured through their labels).
- 10 px text: notification badge 11 px; graph and lineage labels 12 px, and the graph scrolls on phones instead of
  shrinking its labels to about 5 px.

Found by reviewing the screenshots, all fixed:
- Dashboard card "Not available yet · plan Step 7" claimed no detector was installed. Replaced with **Recent
  inferences**, real findings across investigations (new `GET /findings`, tested), each a method's reading, not a verdict.
- The investigation overview's modules panel said status "arrives with T-MIR (plan Step 3)". It now shows the latest
  run: job, state, modules finished, modules by state.
- Evidence header on phones: "Preserved" and "Download original" were drawn over each other; the header now wraps.
- Evidence Analysis rows on phones cut off "Completed" at the right edge.
- Activity times ("just now") wrapped onto two lines; the time column is wider and does not wrap.

Not covered: colour contrast was not measured; no screen-reader walkthrough; tablet widths only through the phone and
desktop breakpoints.

## Step 9: validation and hardening — 27 November 2026

| Check | Actual result |
|---|---|
| Backend suite, this machine | **274 passed** in 183 s |
| Backend suite, **clean Docker image** (`docker compose --profile ci run --rm tests`) | **254 passed, 9 skipped** in 91 s. Skips: PyTorch not installed (1), detector weights absent (7), Neo4j not reachable (1) |
| Playwright | **21 passed** in 2.2 min |
| Containerised stack (`--profile app`, own database) | API ready, v1.0.0; upload → 12-module run (PARTIALLY_COMPLETED: no detectors in the lean image) → DRAFT report GENERATED; worker alive; production web 200 with CSP and `X-Frame-Options: DENY`, rendered with no console errors |
| `test_security.py` | 4 passed: foreign-Origin upload and case creation refused (403) with nothing stored, same-site and Origin-less writes accepted; protective headers; 4th write in a minute → 429 with `Retry-After`; production without authentication refused |
| `test_backup_restore.py` | 3 passed: encrypted backup (no plaintext left), restore into a new database verified by row counts and evidence SHA-256; non-empty target, wrong key, one flipped byte and truncation refused; 3-chunk and empty-file round trips |
| Restore drill, live data | 22 tables, 7,858 rows, 84 evidence: restored copy verified, 84 of 84 hashes equal |
| Outage drill (`Scripts/Testing/OutageDrill.py`) | PostgreSQL down: ready 503 in 3 s, write 503 and not stored, worker up; back: ready in 0.6 s, run completed. Neo4j down: runs complete, lag reported; back: lag 0 in 17 s |
| Dependency audit | pip-audit 88 packages: none known vulnerable (torch/torchvision not checkable); npm audit: 0 (frontend, test tooling) |

Performance (`Benchmarks/Performance/ApiBenchmark.py`, 226 cases / 87 evidence stored, Ryzen 7 260):

| Measure | 1 client | 16 concurrent clients |
|---|---|---|
| `GET /cases` (50) p50 / p95 | 31 / 99 ms | 31 / 119 ms |
| `GET /evidence` (50) p50 / p95 | 31 / 78 ms | 65 / 206 ms |
| `GET /cases/{id}/summary` p50 / p95 | 31 / 51 ms | 53 / 178 ms |
| `GET /search` p50 / p95 | 33 / 73 ms | 40 / 156 ms |
| Upload, validated and hashed | 25 MB in 0.26 s; 200 MB in 1.02 s (195 MB/s) | |
| Image run, 1024×768 JPEG, 12 modules, detectors on | 1.04–1.18 s running time | |

Found and fixed during Step 9:
- CORS did not stop a hostile page from **submitting** a cross-site multipart upload; the Origin guard now does.
- The clean image lacked `VERSION` and the flowchart document the registry tests read; the local machine hid both.
- The frontend folder was `frontend` on disk but `Frontend` in Git; Docker's case-sensitive build context failed on it.
  Renamed to match Git (and the dev-server configuration with it).
- The detector unit tests imported PyTorch at collection time; they now skip with the reason when it is absent.

Not covered: the CI workflow has not run (nothing pushed); no authentication; live storage and database are not
encrypted at rest; performance was measured on one machine with local data, not under sustained load.

## Step 8: remaining integration — 26 November 2026

| Check | Actual result |
|---|---|
| Backend suite (`pytest Tests --ignore=Tests/End-To-End`) | **267 passed** in 171 s |
| Playwright (`NEXTRON_API=http://localhost:8001/api/v1`) | **21 passed** in 1.7 min |
| `Integration/API/test_step8.py` | 5 passed: preferences start at version 0 (defaults) and save as version 1 with untouched fields kept; a save based on version 0 after that is refused (409 `PREFERENCES_CONFLICT`, current version 1) and nothing is applied; unknown keys and values give 422; one `preferences.updated` event per save; automatic analysis off → upload queues no run, back on → it does; completed and partial runs turned off → no such notifications; reading a notification publishes one `notification.read` (not again if already read); search returns evidence, source, review, report and a finding linked to its evidence; `100%_` matches nothing (wildcards literal); `/system/config` contains no database address, password or storage path |
| `step8-integration.spec.ts` | Two tabs on Settings: a save in one unticks the box in the other through live events; the other tab's edit based on the old version is refused, it says so, and shows the stored values. A dropped live connection (closed through `routeWebSocket`): the status chip says "Reconnecting", the client reconnects with `?after=<n>`, an investigation created meanwhile appears without a reload. Ctrl K search finds a source and opens it |

Failures found and fixed:
- The Settings form measured unsaved changes against the newest stored document instead of the one it was loaded
  from, so another tab's save looked like a local edit and the form refused to follow it. It now keeps its base version
  and document.
- `/system/config` reported Qdrant as deferred after the visual-search work had added it; it now reads `QDRANT_URL`.
  Its web-search key check failed on test settings that hold the key as a plain string.
- Stale expectations: search "not searchable yet" (now every type is searched), migration head 0009.
- One Playwright run failed only because the dev API was still the previous build; restarting it fixed it.

Not covered: preferences are per operator, and there is one operator; reconnect was exercised by closing the socket,
not by stopping the API process; search uses ILIKE without ranking or full-text indexes.

## Step 7 and the Neo4j projection — 26 November 2026

| Check | Actual result |
|---|---|
| Backend suite (`pytest Tests --ignore=Tests/End-To-End`) | **262 passed** in 288 s (includes the visual-search tests added in parallel) |
| Playwright (`NEXTRON_API=http://localhost:8001/api/v1`) | **18 passed** in 1.9 min |
| `Integration/Orchestration/test_investigation.py` | 2 passed: graph has a supporting record on every edge; reconstruction holds the file's claimed EXIF time and NEXTRON's receipt; FINAL refused before a conclusion (`CONCLUSION_REQUIRED`), conclusion refused before a reconstruction (`RECONSTRUCTION_REQUIRED`); review versions 1 → 2 with the latest current; DRAFT and FINAL generated, PDF starts `%PDF`, both downloads match their recorded SHA-256; `UPDATE reviews`, `DELETE graph_snapshots`, `DELETE reports` rejected by triggers; a file claiming creation after its source's stated publication gives one TIME_CONFLICT |
| `Integration/Projection/test_neo4j.py` (real Neo4j 5.26.34 container) | 2 passed: idle tick projects exactly the snapshot's nodes and edges; a second tick changes nothing; a new snapshot replaces the subgraph; lag reaches 0; rebuild re-projects from PostgreSQL; disabled projection reported as such (`PROJECTION_UNAVAILABLE`). The test removes its case's nodes afterwards |
| `step7-investigation.spec.ts` | Upload → graph and reconstruction appear → case conclusion recorded in the Review tab → FINAL report generated by the worker → downloaded PDF's SHA-256 equals the one on the page |
| Manual check on the running stack | CASE-0098: graph 2 evidence / 15 findings / 22 edges; Neo4j 18 nodes, 22 relationships, lag 0; RPT-0001 PDF SHA-256 `455c9cc6…a0ce` equals the downloaded file |

Failures found and fixed:
- The real-worker subprocess test read `Backend/.env`, so it ran the installed speech detector and could reach the shared
  Neo4j. It now sets `DETECTORS_ENABLED=false` and an empty `NEO4J_URI`, as `build_app` does.
- Two Step 3 browser expectations assumed runs end partial because NEX-EGC was not built. Every module now runs, so
  runs on this stack complete. The retry test now makes its own partial run (a 1-second video: no evaluated video
  detector is installed), and expects the retry under "Needs attention".
- Stale expectations: migration head 0007, plan states for EGC/REC, 20 module events per image run, catalogue with no
  NOT_IMPLEMENTED modules.
- The dev server kept serving a deleted module after `PendingPages.tsx` was removed (it runs from the lowercase
  `frontend\Web` path); restarting it fixed it. A code fault was not involved.

Not covered: reports are checked for structure, hashes and the frozen summary, not for layout; NEX-REC orders dated
statements and detects one kind of conflict, not full event reconstruction; reviewer roles do not exist (single local
operator); Qdrant remains deferred.

## Visual search and opt-in web lookup — 26 November 2026

| Check | Actual result |
|---|---|
| Full backend suite | `python -m pytest Tests -q`: **262 passed, 1 warning** (Pillow's deliberate decompression-bomb fixture) in 209.67 s |
| SerpApi adapter, thumbnails and API branch | Focused suite: **10 passed**; mocked Free Plan check, consent, upload, result mapping, preview token, metadata stripping and error handling |
| Browser, real frontend and API | `playwright test Specs/visual-search.spec.ts`: **2 passed**; local default, web consent and rendered in-app preview (the browser web result is a fixture) |
| Complete browser suite | `playwright test`: **18 passed** in 1.6 minutes against the running API, worker and frontend |
| Live provider | Account endpoint returned **Free Plan**, price 0, 250 searches left initially. Two explicit searches of a generated image returned **HTTP 200, five web leads each**; two of three fetched previews returned HTTP 200, one source returned 404 and the UI retained its link fallback. The account had 248 free searches left afterward. No private evidence was sent. |
| Live app status | `/api/v1/health/ready` succeeded; `/api/v1/visual-search/status` reported local Qdrant reachable and web configured. |

The live request proves the configured provider path works; it does not prove comprehensive web coverage or that a result is the original source. Returned provider matches are unscored investigation leads.

During the broad browser run, the job monitor hid an older partial job after 15 newer jobs arrived. It now shows partial and failed jobs in a dedicated attention section. A T-MIR test also expected an obsolete "completed partially" notification; it now checks the notification for the job created by that test. Both targeted checks and the final 18-test browser run passed.

The API remained ready with Qdrant reachable and the web provider configured after testing. Its Windows asyncio log recorded six `ConnectionResetError` messages when browser tests closed WebSocket connections; no visual-search request failed. These transport messages remain a known Windows development-server log issue.

## Steps 5 and 6, and the detector benchmark — 26 November 2026

Backend tests and browser tests are listed in the final lines of this section once the last run completes.

| Check | How | Result |
|---|---|---|
| Detector benchmark | `Benchmarks/Detectors/RunBenchmark.py` on 500 images and 800 speech clips, CPU | See [Detector Benchmark](Detector%20Benchmark.md): Community Forensics AUC 0.997 (chosen for images); SSL-AASIST DF AUC 0.966 (chosen for speech); SPAI stopped (230 s per camera photo) |
| SSRF (Step 5 "done when") | `Tests/Unit/Backend/test_safe_fetch.py`, 47 tests | Loopback, private, link-local and metadata (169.254.169.254), CGNAT, multicast, reserved, IPv4-mapped IPv6 and decimal/hex/octal/short spellings refused before connecting; redirect to an internal address refused; redirect limit and streaming size limit enforced; platform URLs never requested |
| Fingerprint precision/recall (Step 5 "done when") | `Benchmarks/Fingerprints/ControlledSet.py`: 60 real photos × 5 benign variants + 120 distractors (1,080 positive, 66k negative pairs) | At the chosen pHash ≤ 12 and dHash ≤ 16: **precision 1.00, recall 0.91**; by variant: half size 0.96, JPEG q60 0.94, 10 % crop 0.71, +20 % brightness 1.00, 5 px border 1.00. Closest pair of unrelated photos: pHash 12 but dHash > 20 |
| Sources → evidence → lineage | `Tests/Integration/Orchestration/test_sources_lineage.py` (worker, local web server) | Direct media and Open Graph media retrieved and preserved with custody; 404 → NOT_FOUND; refresh adds a revision; three copies of one photo give three CANDIDATE relationships; the copy whose source claims the earlier time is "earlier observed"; a still matches the frame of its video at ≥ 2 s; relationships cannot be deleted, observations cannot be changed |
| Correlation ground truth (Step 6 "done when") | `Tests/Integration/Orchestration/test_correlation.py` | Trim from 3.0 s: video offset within ±0.5 s and audio within ±0.05 s, speed 1.00, TRN TRIMMED; replaced audio: TRN AUDIO_REPLACED (and no false TRIMMED); splice at 4.0 s: VID and AUD both within ±0.5 s, CMC COINCIDENT_DISCONTINUITY |

Failures found and fixed:
- Numeric host spellings (`2130706433`, `0x7f000001`, `127.1`) were safe on Windows only because its resolver rejects them; Linux would
  resolve them to 127.0.0.1. They are now parsed like `inet_aton` and checked on every platform. Multicast (224.0.0.0/4) is counted as
  "global" by Python and was let through to a connection attempt; it is now refused explicitly.
- The audio matcher only probed from the start of the first recording, so a copy trimmed at 3 s was missed; it now probes with the shorter
  recording every quarter block.
- Spectral flux missed a noise-to-tone splice (noise has high flux everywhere); a spectral novelty measure (Foote 2000) now finds a change of
  sound character, with its own threshold, and the continuous-recording test still shows no false candidate.
- The DCT hash is unstable on flat synthetic graphics (FFmpeg test patterns); frame matching is tested on photographic content and the
  limitation is stated with every FRAME_OF_VIDEO candidate.
- The detector-verification cache was keyed by expected hash only, so a second file pinned to the same hash skipped the check; it is now keyed
  by path, size and modification time.
- An orphaned Next.js dev server hung after a session restart and timed out every browser test; restarted.

Not covered: platform connectors (none configured); the Neo4j projection (awaiting approval to pull its image); Qdrant (deferred until an
embedding model is adopted); NEX-ALN/TRN run once per case over all pairs rather than one execution per pair.

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
