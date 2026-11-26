# Test Plan

Tests run against real dependencies: PostgreSQL, FFprobe, Pillow, the running API and frontend. No suite mocks
the API, except the end-to-end test that deliberately blocks it to check the unreachable state.

## How to run (from the repository root)

```powershell
docker compose -f Infrastructure/Docker/docker-compose.yml up -d          # PostgreSQL on 127.0.0.1:5433
.\.venv\Scripts\python.exe -m pytest Tests                                  # backend: unit, API, PostgreSQL
cd frontend\Web; npx tsc --noEmit; npx next build                           # frontend typecheck and build
cd ..\..\Tests\End-To-End; npx playwright test                              # needs API on :8000 and frontend on :8080
```

Backend integration tests create and drop their own `nextron_test_*` databases and a temporary storage root.
The Playwright suite runs against the development stack and creates `[E2E]` investigations there.

## Suites

| Suite | Location | Covers |
|---|---|---|
| Envelope and errors | `Tests/Unit/Backend/test_envelope.py` | Error envelope, request IDs, database-down behaviour, settings validation |
| Acquisition units | `Tests/Unit/Backend/test_acquisition_units.py` | Signature sniffing, filename sanitising, storage key safety, no overwrite, pagination |
| Module catalogue | `Tests/Unit/Backend/test_module_catalog.py` | Catalogue edges, numbering, `/system/modules` |
| Dependency registry | `Tests/Unit/Backend/test_dependency_registry.py` | Edges equal flowchart A1 (parsed from the stored Mermaid), A2 differences, acyclicity, edge types, applicability, run/wait/skip rules, deadlock simulation |
| Contracts | `Tests/Unit/Backend/test_contracts.py` | Finding and result validation, JSON round trip, pinned input references, input fingerprint |
| Health | `Tests/Integration/API/test_health.py` | Liveness, readiness, database status, CORS, OpenAPI |
| Cases | `Tests/Integration/API/test_cases.py` | CRUD, lifecycle, filters, statistics, event cursor |
| Evidence | `Tests/Integration/API/test_evidence.py` | Upload of PNG/JPEG/WAV/MP4, invalid media, size limit, integrity and tamper, preview ranges, download custody, restart survival, immutability, reconciliation |
| Frontend support | `Tests/Integration/API/test_frontend_support.py` | Objectives/category/last activity, global evidence list, search |
| Migrations | `Tests/Integration/PostgreSQL/test_migrations.py` | Single linear history; upgrade/downgrade on a clean database |
| Analysis schema | `Tests/Integration/PostgreSQL/test_analysis_schema.py` | Execution reasons, duplicate-completion guard, job leases, result immutability and supersession, append-only findings/artifacts/outbox, confidence guard |
| End to end | `Tests/End-To-End/Specs/step1-frontend.spec.ts` | Every route, navigation and scope, full evidence workflow in the UI, lifecycle, search, 404s, API unreachable, job monitor |

## Added in later steps

| Step | Tests |
|---|---|
| 3 | Concurrent job claims, lease expiry recovery, retry/cancel/timeout, outbox ordering, WebSocket resume |
| 4 | Engine results on fixtures; UNAVAILABLE when tools are missing |
| 5 | SSRF refusals; fingerprint precision/recall; projection rebuild and lag |
| 6 | Alignment and transformation accuracy on ground truth |
| 7 | Graph traceability; review separation; report versioning |
| 9 | Security, reliability, performance, backup/restore; CI |
