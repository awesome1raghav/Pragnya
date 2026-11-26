# Data Architecture

PostgreSQL is the authoritative store. Neo4j and Qdrant are rebuildable projections added in Step 5, fed only
from the transactional outbox. Original evidence and derived files live in protected storage; the database
holds their keys, hashes and relationships. One Alembic history in `Database/PostgreSQL/Migrations`.

## Tables (migrations 0001–0004)

| Table | Migration | Owner service | Module | Written today | Protection |
|---|---|---|---|---|---|
| `cases` | 0002, 0003 | Case | NEX-CM | Yes | Status via lifecycle actions only |
| `evidence` | 0002 | Evidence | NEX-CAP / EVD | Yes | No DELETE; hash, size, key, case, times immutable |
| `evidence_metadata` | 0002 | Analysis | NEX-MET | Yes | Append-only |
| `investigation_events` | 0002 | all (audit) | — | Yes | Append-only; `sequence` cursor |
| `analysis_jobs` | 0004 | **Job** | — | Step 3 | Lease only while running; claim index on queued jobs |
| `analysis_executions` | 0004 | T-MIR | 12 modules | Step 3 | Reasons required; one COMPLETED per module/scope/fingerprint |
| `analysis_results` | 0004 | Analysis | all modules | Step 3 | Immutable; supersede once |
| `analysis_findings` | 0004 | Analysis | all modules | Step 3 | Append-only; calibrated-only confidence |
| `artifact_records` | 0004 | Evidence (storage) | all modules | Step 3+ | Append-only |
| `outbox_events`, `outbox_checkpoints` | 0004 | Event Publisher | — | Step 3 | Events append-only |
| `source_records`, `source_observations` | planned | Source | NEX-SRC | Step 5 | |
| `media_fingerprints` | planned | Analysis | NEX-FPM | Step 5 | |
| `media_relationships` | planned | T-MIR (Flowchart B) | NEX-MOC | Step 5 | |
| `evidence_nodes`, `evidence_edges` | planned | Evidence Graph | NEX-EGC | Step 7 | |
| `reviews`, `decisions` | planned | Review | NEX-INV | Step 7 | Versioned, separate from findings |
| `reports`, `report_versions` | planned | Report | NEX-RPT | Step 7 | Immutable versions |
| `notifications`, `preferences` | planned | Notification / Settings | — | Steps 3, 8 | |

Generic `analysis_results` + `analysis_findings` replace the archive's per-module tables (`alignment_results`,
`transformation_findings`, `correlation_results`); dedicated tables exist only where queries need them (C-18).

## Storage

| Location under `STORAGE_ROOT` | Holds | Status |
|---|---|---|
| `Temporary/<random>.part` | Uploads while streaming | Implemented |
| `Originals/<case_id>/<evidence_id>` | Preserved originals, read-only | Implemented |
| `Derived/…` | Frames, audio tracks, heatmaps, feature vectors (each an `artifact_records` row) | Step 3+ |
| `Reports/…` | Report PDF/JSON versions | Step 7 |

`Scripts/Maintenance/ReconcileEvidenceStorage.py` reports originals without records, records without originals, and
stale staging files.

## Projections (Step 5)

Outbox → dispatcher → per-consumer checkpoint (`outbox_checkpoints`) → Neo4j (graph, lineage) and Qdrant (embeddings,
only once an embedding model is adopted; perceptual hashes stay in PostgreSQL). Consumers are idempotent, keyed by
canonical PostgreSQL IDs, handle deletions as tombstone events, expose their lag on `/system`, and can be rebuilt
from PostgreSQL. A projection outage degrades graph or similarity views; it never blocks evidence intake.
