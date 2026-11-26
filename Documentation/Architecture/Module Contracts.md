# Module Contracts

Every module communicates through these types, defined in `Backend/App/Contracts/` (Pydantic, schema 1.0)
and enforced again by the database (migration `0004`). They implement the result contract proposed in the
master specification (§5.2), adapted to the persisted model as that section allows.

## Module result envelope — `ModuleResult`

One per module execution, whatever happened. Stored whole in `analysis_results.envelope`.

| Field | Meaning | Rule |
|---|---|---|
| `schema_version` | `"1.0"` | |
| `module_id`, `module_version` | Which module and which version of it ran | `NEX-XXX` format |
| `case_id`, `evidence_ids`, `scope_kind` | What it ran on: one evidence item, a pair, or the case | |
| `job_id`, `execution_id` | Which run and which attempt | |
| `status`, `status_reason` | A terminal execution state, and why for SKIPPED, UNAVAILABLE, FAILED, CANCELLED, PARTIALLY_COMPLETED | Non-terminal statuses are refused; explained states need a reason |
| `input_references` | Exactly what it read: evidence by SHA-256, results by ID and module, artifacts by SHA-256, sources by revision | Unpinned references are refused |
| `findings` | Structured findings (below) | Only COMPLETED or PARTIALLY_COMPLETED results may carry findings; each finding must come from this module and cite covered evidence |
| `confidence`, `confidence_basis` | Result-level confidence | Both or neither |
| `limitations`, `warnings` | What the result cannot show, and what went wrong without failing | |
| `artifacts` | Derived files it produced (`ArtifactRef`, with SHA-256) | |
| `related_evidence` | Other evidence its findings refer to | |
| `dependencies` | For each upstream: edge type, its state, the result read | |
| `tool_versions`, `parameters` | Reproducibility record | |
| `started_at`, `completed_at`, `execution_time_ms` | Timing | completion not before start |
| `errors` | `{code, message, retryable}` | A FAILED result needs at least one |

## Finding — `Finding`

| Field | Meaning | Rule |
|---|---|---|
| `assertion` | `OBSERVATION` (measured), `INFERENCE` (concluded from observations), `INCONCLUSIVE` (ran, cannot decide) | Required |
| `finding_type`, `title`, `description` | What it is, in a code and in words | Code is `UPPER_SNAKE` |
| `measurement` | The observed values in the module's own units | |
| `score`, `score_kind` | The method's raw number and what kind it is: `METHOD_SPECIFIC`, `DISTANCE`, `SIMILARITY`, `CALIBRATED_PROBABILITY` | Both or neither |
| `confidence`, `confidence_basis` | A probability the investigator may read as one | **Only** with a `CALIBRATED_PROBABILITY` score and a stated calibration basis; otherwise null. The database enforces this too |
| `time_range` | Seconds into the media | end not before start |
| `region` | Percent of the image or frame, origin top-left | Inside the image |
| `supporting_artifact_ids`, `limitations`, `parameters` | Evidence for the finding and its caveats | |

## Artifacts and input references

- `ArtifactRef`: kind (`FRAME`, `FRAME_SET`, `AUDIO_TRACK`, `THUMBNAIL`, `HEATMAP`, `FEATURE_VECTOR`, `FINGERPRINT`,
  `REPORT_PDF`, `REPORT_JSON`, `OTHER`), SHA-256, size, MIME type, and what it was derived from. Storage keys stay
  on the server. `artifact_records` rows are immutable.
- `InputReference`: `EVIDENCE` and `ARTIFACT` are pinned by SHA-256, `MODULE_RESULT` by result ID and producing module,
  `SOURCE_RECORD` by revision.
- `input_fingerprint(module_id, module_version, parameters, inputs)`: SHA-256 over a canonical form; the same work
  always gives the same fingerprint, regardless of input order (see [Orchestration](Orchestration.md)).

## Execution vocabulary

`ExecutionState`, `SkipReason`, `FailureReason`, `JobState`, `JobType`, `ScopeKind` in
`Backend/App/Contracts/ExecutionStates.py`. Value sets are defined once on the database models and asserted equal.

## What the database adds

| Table | Guarantee |
|---|---|
| `analysis_executions` | Explained states need a reason; terminal states need a finish time; one COMPLETED row per module, scope and input fingerprint |
| `analysis_jobs` | A lease exists only while RUNNING; finish time only when terminal; attempts within the limit |
| `analysis_results` | Immutable; may be marked superseded once; cannot be deleted |
| `analysis_findings` | Append-only; confidence only when calibrated with a basis; score and kind together |
| `artifact_records` | Append-only; SHA-256 required; a parent evidence or artifact (except report files) |
| `outbox_events` | Append-only; dotted lowercase event types (`analysis.module.completed`) |
