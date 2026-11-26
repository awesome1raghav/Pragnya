# Orchestration (T-MIR)

T-MIR coordinates the execution of the twelve modules A1 marks with dotted arrows: NEX-MET, IMG, VID, AUD,
PRV, FPM, MOC, ALN, TRN, CMC, EGC and REC. It is not a forensic engine: it plans, schedules, tracks and
records; the modules do the analysis. The other six modules are owned by domain services (decision D-2).

| What | Where | Status |
|---|---|---|
| Dependency registry, edge types, applicability, run/wait/skip decisions | `Backend/App/Orchestration/TMir/DependencyRegistry.py` | **Implemented (Step 2)** |
| Contracts (states, findings, artifacts, result envelope, input fingerprint) | `Backend/App/Contracts/` | **Implemented (Step 2)** |
| Tables: jobs, executions, results, findings, artifacts, outbox | migration `0004` | **Schema only (Step 2)** |
| Planner, executor, worker, Job Service, outbox dispatcher, WebSocket | — | Step 3 |

## Ownership

| Module | Executed by | Trigger | T-MIR's role |
|---|---|---|---|
| NEX-CM, NEX-CAP, NEX-EVD | Case / Evidence services, in the API request | Investigator | Observes their events; a preserved evidence item can start a run |
| NEX-MET … NEX-PRV, NEX-FPM | **T-MIR**, once per evidence item | Run plan | Executes |
| NEX-MOC, NEX-CMC, NEX-EGC, NEX-REC | **T-MIR**, once per case | Run plan | Executes |
| NEX-ALN, NEX-TRN | **T-MIR**, once per pair MOC proposes | Run plan | Executes |
| NEX-SRC | Source Service, `SOURCE_RESOLUTION` job | Investigator adds or refreshes a URL | Reads committed source records; re-plans FPM, MOC, EGC when they change |
| NEX-INV | Review Service, human decisions | Investigator | None; REC completion makes case-level review possible |
| NEX-RPT | Report Service, `REPORT_GENERATION` job | Investigator | None; warns if a report would cite superseded results |

## Dependency registry

Generated from the registry (do not edit by hand; regenerate if the registry changes). The test
`Tests/Unit/Backend/test_dependency_registry.py` proves these 31 edges equal A1's solid arrows.

| # | From | To | Type | Why |
|---:|---|---|---|---|
| 1 | NEX-CM | NEX-CAP | REQUIRED | Evidence is acquired into an existing case |
| 2 | NEX-CAP | NEX-EVD | REQUIRED | Only validated acquisitions are preserved |
| 3 | NEX-EVD | NEX-MET | REQUIRED | Analysis reads the preserved original |
| 4 | NEX-EVD | NEX-IMG | REQUIRED | Analysis reads the preserved original |
| 5 | NEX-EVD | NEX-VID | REQUIRED | Analysis reads the preserved original |
| 6 | NEX-EVD | NEX-AUD | REQUIRED | Analysis reads the preserved original |
| 7 | NEX-EVD | NEX-PRV | REQUIRED | Analysis reads the preserved original |
| 8 | NEX-MET | NEX-FPM | OPTIONAL | Container facts refine fingerprinting; fingerprints are possible without them |
| 9 | NEX-IMG | NEX-FPM | CONDITIONAL | Image features, when the evidence is an image |
| 10 | NEX-VID | NEX-FPM | CONDITIONAL | Frame and temporal features, when the evidence is a video |
| 11 | NEX-AUD | NEX-FPM | CONDITIONAL | Audio features, when the evidence has audio |
| 12 | NEX-SRC | NEX-FPM | OPTIONAL | Source-retrieved media widens the searched corpus |
| 13 | NEX-FPM | NEX-MOC | REQUIRED | Lineage is built from fingerprint candidates |
| 14 | NEX-SRC | NEX-MOC | OPTIONAL | Source records supply publication times for lineage (A1 only; conflict C-2) |
| 15 | NEX-MOC | NEX-ALN | REQUIRED | Alignment runs on the version pairs lineage proposes |
| 16 | NEX-IMG | NEX-ALN | CONDITIONAL | Image features, for image pairs |
| 17 | NEX-VID | NEX-ALN | CONDITIONAL | Frame features, for video pairs |
| 18 | NEX-ALN | NEX-TRN | CONDITIONAL | Time mapping, for time-based pairs |
| 19 | NEX-MOC | NEX-TRN | REQUIRED | Transformations are analysed between proposed versions |
| 20 | NEX-IMG | NEX-CMC | OPTIONAL | Image findings to correlate |
| 21 | NEX-VID | NEX-CMC | OPTIONAL | Video findings to correlate |
| 22 | NEX-AUD | NEX-CMC | OPTIONAL | Audio findings to correlate |
| 23 | NEX-PRV | NEX-CMC | OPTIONAL | Provenance observations to correlate |
| 24 | NEX-TRN | NEX-CMC | OPTIONAL | Transformation hypotheses to correlate |
| 25 | NEX-SRC | NEX-EGC | OPTIONAL | Source nodes |
| 26 | NEX-MOC | NEX-EGC | OPTIONAL | Version-relationship edges |
| 27 | NEX-TRN | NEX-EGC | OPTIONAL | Transformation-hypothesis nodes and edges |
| 28 | NEX-CMC | NEX-EGC | OPTIONAL | Support and contradiction edges |
| 29 | NEX-EGC | NEX-REC | REQUIRED | Reconstruction orders the evidence graph |
| 30 | NEX-REC | NEX-INV | REQUIRED | Case-level conclusions review a reconstruction |
| 31 | NEX-INV | NEX-RPT | OPTIONAL | A DRAFT report needs no review; a FINAL report requires it (enforced by the Report Service) |

| Module | Owner | Scope | Resources | Applies when | Needs at least one of |
|---|---|---|---|---|---|
| NEX-CM Case Management | DOMAIN_SERVICE | REQUEST | NONE | Always: the investigation entry | — |
| NEX-CAP Evidence Acquisition | DOMAIN_SERVICE | REQUEST | LIGHT | When the case accepts evidence (not archived) | — |
| NEX-EVD Evidence Preservation | DOMAIN_SERVICE | REQUEST | LIGHT | After a valid acquisition | — |
| NEX-MET Metadata Intelligence | T-MIR | EVIDENCE | LIGHT | Every preserved evidence item | — |
| NEX-IMG Image Forensics | T-MIR | EVIDENCE | GPU_OPTIONAL | Image evidence | — |
| NEX-VID Video Forensics | T-MIR | EVIDENCE | GPU_OPTIONAL | Video evidence | — |
| NEX-AUD Audio Forensics | T-MIR | EVIDENCE | CPU_HEAVY | Audio evidence, or video evidence (the module itself reports NOT_APPLICABLE when a video has no audio stream) | — |
| NEX-PRV Provenance Intelligence | T-MIR | EVIDENCE | LIGHT | Formats the C2PA SDK can read (provisional list); absent credentials are a result, not a skip | — |
| NEX-SRC Source Intelligence | SOURCE_JOB | JOB | LIGHT | When an investigator adds or refreshes a source URL (A1 defines no upstream; plan decision D-13) | — |
| NEX-FPM Fingerprint & Similarity | T-MIR | EVIDENCE | CPU_HEAVY | Every evidence item once at least one media engine produced output for it | NEX-IMG, NEX-VID, NEX-AUD |
| NEX-MOC Media Lineage | T-MIR | CASE | LIGHT | When FPM produced fingerprints in the case | — |
| NEX-ALN Temporal Alignment | T-MIR | PAIR | CPU_HEAVY | Each comparable pair MOC proposed | — |
| NEX-TRN Transformation Analysis | T-MIR | PAIR | CPU_HEAVY | Each pair MOC proposed | — |
| NEX-CMC Cross-Modal Correlation | T-MIR | CASE | LIGHT | When at least one of IMG, VID, AUD, PRV or TRN produced output | NEX-IMG, NEX-VID, NEX-AUD, NEX-PRV, NEX-TRN |
| NEX-EGC Evidence Graph Construction | T-MIR | CASE | LIGHT | Always: evidence and case records exist; upstream results add nodes and edges | — |
| NEX-REC Timeline & Reconstruction | T-MIR | CASE | LIGHT | When the evidence graph was built | — |
| NEX-INV Review & Decision | HUMAN_REVIEW | HUMAN | NONE | Findings can be reviewed as soon as they exist; case conclusions need a completed reconstruction | — |
| NEX-RPT Reporting | REPORT_JOB | JOB | LIGHT | On request: DRAFT any time; FINAL only with the review a policy requires | — |

## Deciding whether a module runs

`DependencyRegistry.decide(module, applicable=…, upstream=…, upstream_applicable=…)` returns **RUN**, **WAIT** or
**SKIP** (with a reason) and the limitations to record. The rules, in order:

1. Not applicable to this scope → `SKIP / NOT_APPLICABLE` (e.g. audio forensics on an image).
2. For each incoming edge:
   - **REQUIRED**: upstream not in the run → `SKIP / NO_INPUT`; still pending → wait; ended without output →
     `SKIP / UPSTREAM_FAILED` (or `NO_INPUT` when it was itself skipped or unavailable). A required failure
     decides at once, even while other upstreams are still running.
   - **CONDITIONAL**: ignored when the upstream does not apply to this scope; otherwise wait while pending, use if
     it produced output, record a limitation if not.
   - **OPTIONAL**: wait while pending, use if present, record a limitation if absent or failed.
3. `require_any` (FPM, CMC): if none of the named upstreams produced output and none is still pending →
   `SKIP` (`UPSTREAM_FAILED` when one of them failed, else `NO_INPUT`).
4. Any upstream still pending → **WAIT**; otherwise **RUN**, reading the upstreams in `using`.

A partially completed upstream counts as output and adds a limitation. Domain-service upstreams (CM, CAP, EVD)
are passed as COMPLETED once their records exist. For a case-scope module the planner (Step 3) combines the
per-evidence executions of an upstream into one state: output if any evidence produced output, pending if any is
pending, otherwise the terminal state.

**No deadlock:** the test `test_no_run_can_deadlock` simulates 900 runs (image, video and audio evidence, random
module outcomes, with and without sources) and proves that once every upstream has ended, no module is left waiting.

## Execution lifecycle

Module executions use the states of Flowchart B §5.1 plus `UNAVAILABLE` (conflict C-10):

```
PENDING → QUEUED → WAITING_FOR_DEPENDENCIES → RUNNING → COMPLETED | PARTIALLY_COMPLETED | FAILED | CANCELLED
PENDING → SKIPPED (reason: NOT_APPLICABLE, UPSTREAM_FAILED, NO_INPUT, SUPERSEDED, CANCELLED)
PENDING → UNAVAILABLE (the module's tool or model is not installed or licensed)
```

FAILED, CANCELLED, SKIPPED, UNAVAILABLE and PARTIALLY_COMPLETED must carry a `state_reason`; the database rejects
them without one. Jobs use QUEUED → RUNNING → COMPLETED | PARTIALLY_COMPLETED | FAILED | CANCELLED.

## Control versus data (decision D-4)

- **Control** (the dotted arrows): T-MIR creates executions, schedules them, cancels them and records their state.
- **Data** (the solid arrows): a module never calls another. It reads upstream results from PostgreSQL by ID,
  listed in its `input_references`, each pinned to a result ID, evidence SHA-256 or source revision.
- **Duplicate prevention and re-execution** (D-8, D-14): an execution's `input_fingerprint` is the SHA-256 of
  module version + parameters + pinned inputs. The database allows only one COMPLETED execution per module,
  scope and fingerprint; a resumed or repeated run reuses it. New evidence or a changed source changes the
  fingerprints of the affected case-level modules, so they run again, and their old results are marked superseded.

## How a run executes (Step 3)

Code: `Backend/App/Orchestration/TMir/` (`Planner.py`, `Runner.py`, `Executors.py`, `Recording.py`, `Service.py`) and
`Backend/App/Workers/` (`JobService.py`, `Worker.py`).

1. **Queue.** An upload queues an `INVESTIGATION_RUN` for its evidence in the same transaction as the evidence row
   (`AUTO_ANALYZE_ON_UPLOAD`). `POST /evidence/{id}/analyze` and `POST /cases/{id}/runs` queue one on request (202).
2. **Claim.** A worker claims the next runnable job with `FOR UPDATE SKIP LOCKED` (priority, then age), sets its
   lease and increments `attempt`. A heartbeat thread renews the lease every `JOB_HEARTBEAT_SECONDS`.
3. **Plan.** On the first attempt the planner stores the plan on the job: one entry per evidence item for MET, IMG,
   VID, AUD, PRV and FPM (marked applicable or not from the evidence record), one case entry each for MOC, CMC, EGC
   and REC, and one `<case>:pairs` placeholder for ALN and TRN. Entries are in topological order.
4. **Run each entry.** `decide()` from the registry, with the upstream states of the entry (an evidence-scoped
   upstream of a case-scoped module is aggregated over the run's evidence). SKIP becomes a SKIPPED execution with
   its reason. A module with no executor yet becomes UNAVAILABLE / `MODULE_NOT_IMPLEMENTED`. Otherwise the input
   fingerprint is computed; an existing COMPLETED execution with the same module, scope and fingerprint is
   **reused** (no new work, recorded on the plan entry); else a RUNNING execution is opened, the module runs under
   `MODULE_TIMEOUT_SECONDS` with no transaction held, and one transaction then writes the module's own records
   (NEX-MET: the metadata version and custody event), the execution's end, its result envelope, its findings, the
   plan update and the outbox events.
5. **Finish.** COMPLETED if every entry completed or was skipped; FAILED if nothing produced output and something
   failed; otherwise PARTIALLY_COMPLETED. Today every image run is PARTIALLY_COMPLETED because NEX-IMG, NEX-PRV and
   NEX-EGC are not built yet; that is reported, not hidden.

Every execution that ends gets exactly one result envelope, so a skipped or unavailable module is as visible as a
completed one.

## Leases, fencing and recovery

- **Fencing.** Every runner transaction updates the job row `WHERE lease_owner = me AND state = 'RUNNING'`. A worker
  that stalled past its lease and was replaced cannot write anything more for that job (tested).
- **Crash recovery.** Each worker, before claiming, runs `recover_expired`: RUNNING jobs whose lease ran out get
  their RUNNING executions closed as FAILED / `LEASE_EXPIRED` (with envelopes), the affected plan entries go back to
  PENDING, and the job is requeued with backoff (or FAILED once `max_attempts` is used, or CANCELLED if cancellation
  was requested). Because a module's records and its execution's completion commit together, a crash either left
  nothing (the module runs again as a new attempt) or left everything (the entry is already COMPLETED and is not
  re-run). The partial unique index refuses a second COMPLETED execution for the same inputs in any case; a
  concurrent duplicate is recorded as SKIPPED / SUPERSEDED and uses the other run's result.
- **Retry.** An infrastructure error in the runner (not a module failure) requeues the job after
  `JOB_RETRY_BASE_SECONDS × 2^(attempt−1)`. `POST /jobs/{id}/retry` queues a new job; completed work is reused.
- **Cancel.** A QUEUED job is cancelled at once. A RUNNING job is flagged; the runner stops before its next module and
  records the remaining entries as CANCELLED.
- **Timeouts.** A module that exceeds `MODULE_TIMEOUT_SECONDS` fails with TIMEOUT (its thread is abandoned and nothing
  it returns is written). A job past `JOB_TIMEOUT_SECONDS` since its first start stops before its next module,
  records the rest as CANCELLED / `JOB_TIMEOUT` and ends FAILED.

## Events

Services publish to the outbox in the same transaction as their change: `case.created|updated|archived|reopened`,
`evidence.created`, `evidence.integrity_match|mismatch|missing`, `job.queued|started|retry_scheduled|cancel_requested|
completed|partially_completed|failed|cancelled`, `analysis.module.started|completed|partially_completed|failed|
skipped|unavailable|cancelled|reused`. The dispatcher in each API process polls the outbox with a gap-safe cursor
(an identity value that commits late is waited for up to 15 s; one consumed by a rollback is then skipped),
lets the notification consumer turn job outcomes and failed integrity checks into notifications, then fans the
events out to WebSocket clients.

## Known limitations

- Case-scoped modules aggregate the evidence entries of their own run only. A run started for one upload does not
  yet read other evidence's results; whole-case runs (`POST /cases/{id}/runs`) cover all evidence.
- A timed-out module's thread cannot be killed in-process; it finishes in the background and is ignored. Process
  isolation for heavy engines is a Step 4 decision.
- Graceful worker stop finishes the current job first; a hard-killed worker's job waits for its lease to expire
  (`JOB_LEASE_SECONDS`, 30 s by default) before another worker recovers it, and `/system/workers` keeps counting a
  killed worker as alive until its heartbeat is older than the lease window.
