# API Contracts

The NEXTRON REST API at `http://localhost:8000/api/v1`. The live, authoritative description is the OpenAPI
document at `/openapi.json` (interactive at `/docs`). The frontend mirrors its shapes in
`Frontend/Web/src/api/types.ts`; change both together.

## Conventions

| Topic | Rule |
|---|---|
| Success | `{ "success": true, "message": …, "data": …, "meta": { "request_id", "timestamp" } }` |
| Lists | `data` is an array plus `pagination: { page, page_size, total_items, total_pages, has_next, has_previous }`; `page_size` ≤ 100 |
| Event lists | `data` plus `cursor: { after, next_after, has_more, limit }`; pass `after=<sequence>` to continue |
| Errors | `{ "success": false, "error": { "code", "message", "details" }, "meta": … }`; no stack traces |
| Request IDs | Every response carries `X-Request-ID` (a client may send its own, `[A-Za-z0-9._-]{1,64}`) |
| Status codes | 200 read/update · 201 created · 202 accepted (jobs, from Step 3) · 400 · 404 · 405 · 409 lifecycle conflict · 410 stored original missing · 413 · 415 · 422 validation · 500 · 503 dependency unavailable |
| IDs | UUIDs in paths; display numbers `CASE-0001`, `EVD-0001`, `JOB-0001` in bodies |
| Times | UTC ISO 8601 |
| Fields | snake_case; enums in UPPER_SNAKE |
| Access | Single local operator, no authentication; the API listens on 127.0.0.1 only; CORS allows the frontend origins |

Error codes in use: `VALIDATION_ERROR`, `NOT_FOUND`, `METHOD_NOT_ALLOWED`, `CASE_NOT_FOUND`, `CASE_ARCHIVED`,
`CASE_NOT_ARCHIVED`, `EVIDENCE_NOT_FOUND`, `EVIDENCE_FILE_MISSING`, `METADATA_NOT_FOUND`, `INVALID_UPLOAD`,
`UPLOAD_TOO_LARGE`, `UNSUPPORTED_MEDIA_TYPE`, `INVALID_MEDIA_FORMAT`, `MEDIA_PROBE_UNAVAILABLE`,
`PRESERVATION_FAILED`, `STORAGE_UNAVAILABLE`, `DATABASE_UNAVAILABLE`, `SERVICE_NOT_READY`, `INTERNAL_ERROR`.

## Implemented endpoints (from the running OpenAPI document)

| Method | Path | Summary | Domain |
|---|---|---|---|
| GET | `/health` | Liveness | Health |
| GET | `/health/ready` | Readiness | Health |
| GET | `/system/modules` | Investigation modules and connectivity | System |
| GET | `/system/storage` | Evidence storage status | System |
| GET | `/system/database` | PostgreSQL status | System |
| POST | `/cases` | Create case | Cases (NEX-CM) |
| GET | `/cases` | List cases | Cases (NEX-CM) |
| GET | `/cases/statistics` | Case statistics | Cases (NEX-CM) |
| GET | `/cases/{case_id}` | Get case | Cases (NEX-CM) |
| PATCH | `/cases/{case_id}` | Update case fields | Cases (NEX-CM) |
| POST | `/cases/{case_id}/archive` | Archive case | Cases (NEX-CM) |
| POST | `/cases/{case_id}/reopen` | Reopen case | Cases (NEX-CM) |
| GET | `/cases/{case_id}/summary` | Case overview | Cases (NEX-CM) |
| GET | `/cases/{case_id}/statistics` | Case counts | Cases (NEX-CM) |
| GET | `/cases/{case_id}/events` | Case events (cursor) | Cases (NEX-CM) |
| POST | `/cases/{case_id}/evidence` | Upload evidence (streamed, hashed server-side, preserved) | Evidence |
| GET | `/cases/{case_id}/evidence` | List a case's evidence | Evidence |
| GET | `/evidence` | List evidence across investigations | Evidence |
| GET | `/evidence/statistics` | Evidence counts | Evidence |
| GET | `/evidence/{evidence_id}` | Evidence detail | Evidence |
| GET | `/evidence/{evidence_id}/metadata` | Latest extracted metadata | Evidence |
| GET | `/evidence/{evidence_id}/integrity` | Recorded hash and last verification | Evidence |
| POST | `/evidence/{evidence_id}/verify-integrity` | Recompute SHA-256 of the stored bytes and compare | Evidence |
| GET | `/evidence/{evidence_id}/history` | Custody events (cursor) | Evidence |
| GET | `/evidence/{evidence_id}/preview` | Inline preview of the original bytes (HTTP Range) | Evidence |
| GET | `/evidence/{evidence_id}/download` | Download the original bytes (recorded as a custody event) | Evidence |
| GET | `/search` | Search investigations and evidence | Search |

`GET /system/modules` returns the module catalogue including the 31 typed edges of the dependency registry.

### Step 3: jobs, T-MIR runs, analysis, notifications, live events

| Method | Path | Purpose |
|---|---|---|
| GET | `/jobs` | Jobs, newest first (`state`, `active`, `job_type`, `case_id`, `evidence_id`, paging) |
| GET | `/jobs/{job_id}` | Job detail with measured progress |
| POST | `/jobs/{job_id}/cancel` | Cancel (queued: at once; running: before its next module). 409 `JOB_NOT_CANCELLABLE` |
| POST | `/jobs/{job_id}/retry` | 202: a new job with the same request; completed work is reused. 409 `JOB_NOT_RETRYABLE` |
| POST | `/cases/{case_id}/runs` | 202: queue a T-MIR run (`{"evidence_id": …}` or the whole case). 409 `CASE_ARCHIVED`, `NO_EVIDENCE` |
| GET | `/cases/{case_id}/runs` | A case's runs |
| GET | `/runs/{job_id}` | The run's plan (every module and scope with state and reason) and all its executions |
| POST | `/evidence/{evidence_id}/analyze` | 202: queue a run for one evidence item |
| GET | `/evidence/{evidence_id}/analysis` | Per-module latest execution, current result, recent runs, current findings |
| GET | `/analyses/{result_id}` | A module result envelope (schema 1.0) |
| GET | `/analyses/{result_id}/reproducibility` | Module version, parameters, tool versions, fingerprint, pinned inputs |
| GET | `/analyses/{result_id}/artifacts` | Derived artifacts of a result (none until media engines exist) |
| GET | `/notifications` | Notifications (`unread=true` to filter) |
| GET | `/notifications/summary` | Unread and total counts |
| PATCH | `/notifications/{id}/read` | Mark one read |
| POST | `/notifications/read-all` | Mark all read |
| GET | `/system/workers` | Registered workers, heartbeats, `alive` within the lease window |
| WS | `/ws/events`, `/ws/jobs/{job_id}`, `/ws/cases/{case_id}` | Live outbox events. `?after=<sequence>` replays from PostgreSQL, then streams; without `after` the stream starts now. Messages: `event`, `replay_complete`, `heartbeat`, `pong` |

### Step 4: media engine results and artifacts

| Method | Path | Purpose |
|---|---|---|
| GET | `/cases/{case_id}/modules/{module_id}/results` | One evidence-scoped module (MET, IMG, VID, AUD, PRV, FPM) for every evidence item: latest execution, current result, findings, artifacts, limitations, tool versions. 404 `UNKNOWN_MODULE` |
| GET | `/artifacts/{artifact_id}` | A derived artifact's bytes, inline and inert (`nosniff`, sandboxing CSP), with `X-Artifact-SHA256`. 404 `ARTIFACT_NOT_FOUND`, 410 `ARTIFACT_FILE_MISSING` |

`GET /evidence/{id}/analysis` also returns the `artifacts` of the current results, and `GET /analyses/{id}/artifacts`
returns typed artifact records. Findings carry `region` (percent of the image) or `time_range` (seconds) in their
payload, `score_kind` METHOD_SPECIFIC, and no `confidence` (no method here is calibrated).

### Step 5: sources and lineage

| Method | Path | Purpose |
|---|---|---|
| POST | `/cases/{case_id}/sources` | 202: add a URL; a SOURCE_RESOLUTION job retrieves it. 409 `SOURCE_EXISTS`, `CASE_ARCHIVED`; 422 `INVALID_SOURCE_URL` |
| GET | `/cases/{case_id}/sources`, `/sources` | Sources of a case / across investigations |
| GET | `/sources/{source_id}` | Latest state, claimed publication time, retrieved evidence |
| POST | `/sources/{source_id}/refresh` | 202: retrieve again (new revision). 409 `SOURCE_BUSY` |
| GET | `/sources/{source_id}/history` | Every attempt: outcome, each redirect hop with the address it resolved to, content type, size, media hash |
| GET | `/sources/connectors` | Which connectors exist (generic) and which need approved platform APIs |
| GET | `/cases/{case_id}/lineage` | Nodes (evidence, their sources) and current CANDIDATE relationships with their basis |

Source outcomes: RETRIEVED, METADATA_ONLY, UNAVAILABLE, RESTRICTED, NOT_FOUND, UNSUPPORTED, RATE_LIMITED, BLOCKED (SSRF
rule), FAILED. Retrieved media is preserved as evidence (`source_type` SOURCE_RETRIEVAL) and gets its own run.

### Visual search: local evidence and optional web leads

| Method | Path | Purpose |
|---|---|---|
| GET | `/visual-search/status` | Local model, PostgreSQL and Qdrant readiness; whether the opt-in SerpApi provider is configured. Never returns the API key. |
| POST | `/cases/{case_id}/visual-search` | Multipart image or image `url`, optional JSON `crop`, `top_k` 1–50, and `mode=local|web`. Local searches only the case's indexed evidence. Web requires `allow_external=true` and a configured free-plan SerpApi key; it returns unverified Google Lens leads. |
| GET | `/visual-search/thumbnails/{token}` | Short-lived JPEG preview of a returned web match, fetched by the server under public-address and size limits. A blocked or expired preview returns 404; the source link remains available. |

Web results have `page_url`, `image_url`, `title`, optional `thumbnail_token`, `match_type` (`VISUAL_MATCH` or `EXACT_MATCH_REPORTED`) and null score fields. The provider's exact-match label is not a forensic conclusion. Local results include a cosine similarity score from Qdrant and remain investigation scoped. A web request is never sent implicitly by local search.

Upload responses (`POST /cases/{id}/evidence`) now carry `analysis_job: {job_id, job_number, state}` instead of
`metadata_status`: metadata is extracted by the worker. Per-engine views use `/cases/{case_id}/modules/{module_id}/results`; re-running a module is `POST /evidence/{id}/analyze`
(completed work with unchanged inputs is reused).

### Step 7: graph, reconstruction, reviews, reports, projections

| Method | Path | Purpose |
|---|---|---|
| GET | `/cases/{case_id}/graph` | Latest NEX-EGC snapshot: nodes, edges (each with the `record` that supports it), counts. 409 `GRAPH_NOT_BUILT` |
| GET | `/cases/{case_id}/reconstruction` | Current NEX-REC timeline (RECEIVED, RETRIEVED, CLAIMED_CREATION, CLAIMED_PUBLICATION, each with who states it) and TIME_CONFLICT findings |
| POST | `/cases/{case_id}/reviews` | 201: a decision on a FINDING, RELATIONSHIP or CASE_CONCLUSION (subject = the case), with rationale; version n+1 of that subject. 404 `REVIEW_SUBJECT_NOT_FOUND`; 409 `RECONSTRUCTION_REQUIRED`, `CASE_ARCHIVED` |
| GET | `/cases/{case_id}/reviews?current=` | Every version, newest first; `current=true` keeps the latest per subject |
| POST | `/cases/{case_id}/reports` | 202: `{kind: DRAFT|FINAL}`; a REPORT_GENERATION job writes JSON and PDF. 409 `CONCLUSION_REQUIRED` for FINAL without a reviewed conclusion |
| GET | `/cases/{case_id}/reports`, `/reports/{report_id}` | Versions: state QUEUED/GENERATED/FAILED, SHA-256 of each file, frozen summary |
| GET | `/reports/{report_id}/download?format=pdf|json` | The file, with `X-Report-SHA256`. 409 `REPORT_NOT_READY` |
| GET | `/system/projections` | Neo4j consumer: configured, reachable, checkpoint, latest sequence, lag, pending snapshots, node and relationship counts |
| POST | `/system/projections/neo4j/rebuild` | Re-project every case's latest snapshot from PostgreSQL. 503 `PROJECTION_UNAVAILABLE` |

### Step 8: search, preferences, configuration

| Method | Path | Purpose |
|---|---|---|
| GET | `/search?q=&limit=` | Hits of type CASE, EVIDENCE, SOURCE (URL, title, SRC-n), FINDING (current findings: title, type; with `evidence_id`), REPORT (RPT-n), REVIEW (rationale, REV-n); `searched_types` lists all six |
| GET | `/preferences` | `{operator, version, preferences, effective, updated_at}`; version 0 = defaults, never saved |
| PATCH | `/preferences` | `{version, preferences: <partial>}`; 409 `PREFERENCES_CONFLICT` (with the current document) when `version` is stale; 422 for unknown keys. Publishes `preferences.updated` |
| GET | `/system/config` | Environment, version, operator, upload limit and auto-analysis default, job limits, detectors, projections, web visual search: no secrets |

New outbox events: `preferences.updated`, `notification.read`. Notifications now also come from `source.retrieval_ended`
(failure outcomes), `report.generated` and `report.failed`.

## Planned endpoints (by step)

| Step | Domain → service | Endpoints |
|---|---|---|
| 6 | T-MIR APIs (correlation) | `/cases/{id}/alignment`, `/transformations`, `/correlation` |
