# NEXTRON Backend

FastAPI modular monolith for NEXTRON (archive: `Documentation/NEXTRON Master Project Archive.md`).
Database code lives only in the root `Database/` package; this folder holds the API application.

## Status

| Built and tested | Not built yet |
|---|---|
| App factory, settings, `{success, data, meta}` envelope, error envelope, `X-Request-ID` | A benchmarked face-manipulation video detector (GenD is pinned; needs a licensed face-swap test set) |
| `/health`, `/health/ready` (database + storage), `/system/database`, `/system/storage`, `/system/workers` | Event-level reconstruction beyond dated statements and their conflicts (NEX-REC) |
| NEX-CM cases: create, list/filter/sort/page, get, patch, archive, reopen, summary, statistics, events | Qdrant (no embedding model adopted); Redis is deferred |
| NEX-CAP streamed multipart upload with signature + decode validation | Authentication (single local operator for now; API binds to 127.0.0.1) |
| NEX-EVD SHA-256 while streaming, read-only originals, custody events, verify-integrity, preview (Range), download, history | Reviewer roles (single local operator) |
| NEX-MET FFprobe (video/audio) and Pillow + EXIF (images) metadata, versioned, run by T-MIR in workers | |
| NEX-SRC (SSRF-safe retrieval), NEX-FPM, NEX-MOC; NEX-ALN, NEX-TRN, NEX-CMC | |
| NEX-EGC graph snapshots, NEX-REC timeline and time conflicts, NEX-INV versioned reviews, NEX-RPT JSON + PDF reports (worker job, SHA-256) | |
| Neo4j 5.26 projection kept current by the worker; `/system/projections`, rebuild from PostgreSQL | |
| T-MIR planner and runner; Job Service (claims with SKIP LOCKED, leases, fencing, recovery, retry with backoff, cancel, timeouts); worker process | |
| Transactional outbox, dispatcher, WebSockets, notifications; Job, Run, Analysis and Notification APIs | |
| Media engines NEX-IMG, NEX-VID, NEX-AUD (measurement methods) and NEX-PRV (C2PA SDK); derived artifacts, `GET /artifacts/{id}` | Chromaprint fingerprints (install `fpcalc`; set `FPCALC_PATH`) |
| Migrations `0001` baseline, `0002` cases/evidence/metadata/events with append-only triggers, `0003` case objectives and category, `0004` jobs/executions/results/findings/artifacts/outbox, `0005` workers and notifications, `0006` sources/fingerprints/relationships, `0007` graph snapshots, reviews, reports | |
| Frontend support: `GET /evidence` (all investigations, filters, search), `GET /search`, `GET /system/modules` (module catalogue from flowchart A1), `last_activity_at` on cases | |

## Run it (Windows PowerShell, from the repository root)

```powershell
# 1. PostgreSQL 17 in Docker (first time: copy and edit the two .env.example files)
Copy-Item Infrastructure/Docker/.env.example Infrastructure/Docker/.env
Copy-Item Backend/.env.example Backend/.env
docker compose -f Infrastructure/Docker/docker-compose.yml up -d

# 2. Python 3.11 environment
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r Backend/requirements.txt

# 3. Migrate, then start the API on http://127.0.0.1:8000 (Swagger UI at /docs)
.\.venv\Scripts\python.exe -m alembic -c Database/PostgreSQL/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m uvicorn Backend.App.Main:app --host 127.0.0.1 --port 8000

# 4. At least one worker, in another terminal (uploads queue analysis; without a worker it waits)
.\.venv\Scripts\python.exe -m Backend.App.Workers.Worker

# Optional: pretrained detectors (about 2.6 GB of weights into Backend/Models, pinned by SHA-256 in
# Backend/App/Detectors/Manifest.py; see Documentation/Testing/Detector Benchmark.md). Without them the
# engines still run and say that the detector is not installed.

# 5. Tests (integration tests need the Compose PostgreSQL running)
.\.venv\Scripts\python.exe -m pytest Tests
```

PostgreSQL is published on `127.0.0.1:5433` (not 5432, which a native install may already use).
The password in both `.env` files must match; neither file is committed.

## Run it in containers

```powershell
docker compose -f Infrastructure/Docker/docker-compose.yml --profile app up -d --build
```
API on http://localhost:8100, web on http://localhost:8180, database `nextron_app` (create it first; kept apart from a
natively run API's database). The image is lean: no PyTorch, so detectors and local visual search report themselves
unavailable.

```powershell
docker compose -f Infrastructure/Docker/docker-compose.yml --profile ci run --rm tests
```
Backend suite in a clean image. Backups and restore: [Backup and Recovery](../Documentation/Operations/Backup%20and%20Recovery.md).
Security controls and open gaps: [Security Review](../Documentation/Testing/Security%20Review.md).

## Layout

```text
Backend/App/
├── Main.py            app factory; `app` is the ASGI entry point
├── Config.py          settings from environment / Backend/.env (no default credentials)
├── Lifespan.py        creates and disposes the database engine; runs the outbox dispatcher
├── Dependencies.py    FastAPI dependencies
├── Api/V1/            Router.py, Health.py, System.py, Cases.py, Evidence.py, Search.py, Jobs.py,
│                      Analysis.py (runs, analysis, results), Notifications.py, Realtime.py (WebSockets)
├── Contracts/         ExecutionStates.py, Findings.py, Artifacts.py, ModuleResult.py
├── Orchestration/     ModuleCatalog.py; TMir/ DependencyRegistry.py, Planner.py, Runner.py, Executors.py,
│                      Recording.py, Service.py, Schemas.py
├── Workers/           JobService.py (job state, leases, recovery), Worker.py (the worker process)
├── Realtime/          Outbox.py, Cursor.py (gap-safe), Dispatcher.py, Hub.py, Notifications.py
├── Core/              Exceptions.py (error codes + handlers), Middleware.py, RequestContext.py
├── Schemas/           Common.py (envelopes), Pagination.py, Events.py
├── Modules/
│   ├── NexCm/         Service.py, Lifecycle.py, Schemas.py
│   ├── NexCap/        Service.py, FileAcquisition.py (streaming multipart), Validation.py
│   ├── NexEvd/        Service.py, HashService.py, IntegrityService.py, ChainOfCustody.py,
│   │                  StorageReconciliation.py, Schemas.py
│   ├── NexMet/        Service.py, MetadataExtractor.py, ExifAnalyzer.py, Schemas.py
│   ├── NexImg/ImageAnalyzer.py, NexVid/VideoAnalyzer.py, NexAud/AudioAnalyzer.py, NexPrv/C2paAnalyzer.py
│   └── Engine.py      the EngineOutput contract shared by the media engines
├── Storage/           StorageInterface.py, LocalStorage.py (originals and write-once derived artifacts)
├── Utils/MediaProbe.py, MediaDecode.py   FFprobe / FFmpeg adapters (bounded frame, packet and audio reads)
└── Services/HealthService.py     PostgreSQL probe
```

Database models and query functions live in the root `Database/PostgreSQL/` (`Models/`, `Repositories/`).

## Evidence handling

1. The upload streams into `STORAGE_ROOT/Temporary/<random>.part` while SHA-256 and size are computed;
   the size limit (`MAX_UPLOAD_SIZE_BYTES`) is enforced mid-stream.
2. The bytes must carry a supported image/video/audio signature **and** decode (Pillow) or parse (FFprobe).
   The client's filename and Content-Type are recorded as labels only.
3. The file is moved to `Originals/<case_id>/<evidence_id>`, made read-only, re-hashed, and only then is
   the evidence row committed together with `evidence.received / hashed / preserved` events.
4. Metadata is extracted from the stored original and recorded as a new version with its input hash.
   (This runs in the upload request until Step 3 moves it to a worker job.)

The database rejects UPDATE/DELETE on events and metadata, DELETE on evidence, and any change to an
evidence row's hash, size, storage key, case or timestamps. Check storage against the database with:

```powershell
.\.venv\Scripts\python.exe -m Scripts.Maintenance.ReconcileEvidenceStorage
```

## Health semantics

- `/health` answers whenever the process is running; it touches no dependency.
- `/health/ready` returns 200 only if PostgreSQL is reachable **and** at the migration head;
  otherwise 503 `SERVICE_NOT_READY` with the failing check.
- `/system/database` returns 200 `HEALTHY` (or `DEGRADED` when migrations are behind) with measured
  latency, server version, revisions and this process's pool counts; 503 `DATABASE_UNAVAILABLE` when
  unreachable. Driver error messages are not returned, only the error class and SQLSTATE.
