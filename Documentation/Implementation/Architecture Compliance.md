# Architecture Compliance

How the repository maps onto the two supplied architectures. Updated at the end of each step.

## Architecture A — module connectivity

| Requirement | Where | Compliant |
|---|---|---|
| 18 modules with the given names and IDs | `DependencyRegistry.MODULES` | Yes (tested) |
| A1's 31 solid edges, including `SRC → MOC`, nothing added or removed | `DependencyRegistry.EDGES` | Yes — test parses the stored flowchart |
| T-MIR coordinates A1's 12 modules | `TMIR_COORDINATED`, owner `T-MIR` | Yes (tested) |
| A2's 18 dotted edges | Interpreted as "observes" for CM, CAP, EVD, SRC, INV, RPT (C-1) | Documented deviation |
| Execution states incl. WAITING_FOR_DEPENDENCIES and SKIPPED with explanation | `ExecutionState`; DB requires `state_reason` | Yes, plus UNAVAILABLE (C-10) |
| Optional and inapplicable modules never deadlock a run | `decide()`; deadlock simulation | Yes (tested) |
| Structured findings; observation / inference / inconclusive distinguished | `Finding.assertion` | Yes |
| No arbitrary confidence | Contract and DB constraint | Yes (tested) |
| Findings traceable to module and evidence | `input_references`, `evidence_ids`, execution IDs | Yes (contract); populated from Step 3 |
| Modules implemented | 3 of 18 (+ MET partial) | Steps 3–7 |

## Architecture B — application

| Requirement | Where | Compliant |
|---|---|---|
| 14 routes with a clear purpose | `Frontend/Web/src/app` | Yes; 5 state that their backend is not built |
| Shared shell: navigation, search, job monitor, system status | `Frontend/Web/src/layouts` | Yes |
| Context preserved across global pages | `?case=` + CaseContext | Yes (tested) |
| API domains → services | Case, Evidence, Health done; others Steps 3–7 | Partial |
| Tables: cases, evidence | Implemented | Yes |
| Tables: analysis_jobs, analysis_results | Migration 0004 | Schema only |
| Tables: source_records, media_relationships, evidence_nodes/edges, reports | — | Steps 5, 7 |
| Event publisher → WebSocket → frontend state | Outbox table only | Step 3 |
| No fake data, statistics or health | Real API only; `src/demo` not routed | Yes (tested with API blocked) |

Documented deviations and their reasons: [Architectural Decisions](../Architecture/Architectural%20Decisions.md),
[Application Architecture](../Architecture/Application%20Architecture.md#deliberate-extensions-documented-conflicts).
