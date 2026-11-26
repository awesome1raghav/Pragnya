# Repository Audit

The initial audit (environment, backend stubs, frontend mock contract, documentation conflicts) is in
[Architecture Reconciliation and Revised Plan](Architecture%20Reconciliation%20and%20Revised%20Plan.md) §1.
This page records the repository's state after each step.

## After Step 2 (26 November 2026)

| Area | Contents |
|---|---|
| `Backend/App` | FastAPI app; `Api/V1` (Health, System, Cases, Evidence, Search); `Modules` NexCm, NexCap, NexEvd, NexMet; `Contracts`; `Orchestration` (ModuleCatalog, `TMir/DependencyRegistry`); `Storage`; `Services/HealthService`; `Utils/MediaProbe` |
| `Database/PostgreSQL` | Models for 11 tables; repositories; one Alembic history `0001`–`0004` with append-only and immutability triggers |
| `Frontend/Web` | Next.js 16.4.6 (pinned); real API layer; 14 routes; shell; `src/demo` holds the former mock prototype, not routed |
| `Infrastructure/Docker` | Compose with PostgreSQL 17.12 |
| `Scripts/Maintenance` | `ReconcileEvidenceStorage.py` |
| `Tests` | 134 pytest tests (unit, API, PostgreSQL); `End-To-End` Playwright suite (9 tests) |
| `Documentation` | Master archive; `Architecture/` (7 documents incl. the verbatim flowcharts); `Implementation/` (plan, status, compliance, audit, reconciliation); `Testing/` |

## Known issues

| Issue | Impact | Planned |
|---|---|---|
| Folder on disk is `frontend/`, Git tracks `Frontend/` | Dev server must start from `frontend\Web` | Rename on disk when servers are stopped |
| Root `package.json` declares npm workspaces without a root lockfile | Installs need `--workspaces=false` | Step 9 |
| `Infrastructure/Docker/*.Dockerfile` and CI are stale | No container build or CI tests | Step 9 |
| Dev database contains `[E2E]` investigations from Playwright runs | Test data next to real data | Separate E2E database in Step 9 |
