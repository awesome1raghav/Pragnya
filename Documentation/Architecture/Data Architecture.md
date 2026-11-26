# Data Architecture

PostgreSQL is the authoritative store. Neo4j (Step 7) is a rebuildable projection fed only from the transactional
outbox; Qdrant is deferred until an embedding model is adopted. Original evidence and derived files live in protected storage; the database
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
| `source_records`, `source_observations` | 0006 | Source | NEX-SRC | Yes | Observations append-only; one record per case and normalised URL |
| `media_fingerprints` | 0006 | Analysis | NEX-FPM | Yes | Append-only; one per evidence, kind and algorithm |
| `media_relationships` | 0006 | T-MIR (Flowchart B) | NEX-MOC | Yes | No DELETE; superseded, never removed; status CANDIDATE |
| `graph_snapshots` | 0007 | Evidence Graph | NEX-EGC | Yes | Append-only (trigger); the whole case graph per run, nodes and edges as JSONB, each edge naming its record |
| `reviews` | 0007 | Review | NEX-INV | Yes | Append-only (trigger); unique (subject_type, subject_id, version); rationale required; never alters findings |
| `reports` | 0007 | Report | NEX-RPT | Yes | No DELETE (trigger); unique (case, version); file keys and SHA-256 of JSON and PDF |
| `operator_preferences` | 0009 | Settings | — | Yes | One row per operator; `version` for optimistic concurrency; validated document (notifications, analysis, reports) |

Generic `analysis_results` + `analysis_findings` replace the archive's per-module tables (`alignment_results`,
`transformation_findings`, `correlation_results`); dedicated tables exist only where queries need them (C-18).

## Storage

| Location under `STORAGE_ROOT` | Holds | Status |
|---|---|---|
| `Temporary/<random>.part` | Uploads while streaming | Implemented |
| `Originals/<case_id>/<evidence_id>` | Preserved originals, read-only | Implemented |
| `Derived/…` | Frames, audio tracks, heatmaps, feature vectors (each an `artifact_records` row) | Step 3+ |
| `Reports/<case_id>/<report_id>.{json,pdf}` | Report versions, write-once and read-only, SHA-256 on the `reports` row | Implemented |

`Scripts/Maintenance/ReconcileEvidenceStorage.py` reports originals without records, records without originals, and
stale staging files.

## Projections (Step 7)

Outbox → dispatcher → per-consumer checkpoint (`outbox_checkpoints`) → Neo4j (graph, lineage) and Qdrant (embeddings,
only once an embedding model is adopted; perceptual hashes stay in PostgreSQL). Consumers are idempotent, keyed by
canonical PostgreSQL IDs, handle deletions as tombstone events, expose their lag on `/system`, and can be rebuilt
from PostgreSQL. A projection outage degrades graph or similarity views; it never blocks evidence intake.

Implemented: the Neo4j consumer runs in the worker's idle loop with checkpoint `neo4j` and a gap-safe cursor. For each
case with a `graph.snapshot_created` event it replaces that case's subgraph with the case's latest snapshot in one
transaction (`:NexNode` + `:Case|:Evidence|:Source|:Finding`; relationships CONTAINS, RETRIEVED_AS, CANDIDATE_VERSION,
ABOUT, CITES with their `record`). Replaying is harmless. If Neo4j is down the checkpoint does not move. Cases are never
deleted, so no tombstones are needed yet.
