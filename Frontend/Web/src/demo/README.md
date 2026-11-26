# Demo prototype (not routed)

This folder holds the original mock-data workspace: its contract (`api/contract.ts`), fixtures,
in-memory mock adapter, store, and the screens built on them (dashboard, evidence workbench,
evidence graph, report studio, review, governance).

- **Nothing here is reachable from a route.** Every page in `src/app` now reads the real NEXTRON
  API through `src/api`.
- It is kept for its designs: the graph, report studio, workbench and review screens are reused
  as the corresponding backend modules arrive (plan steps 3–7), rebuilt on real data.
- Everything here is **demo data**: findings, confidence values, readiness percentages, assessment
  ranges and audit "signatures" are fixtures, not results. Never show them as investigation output.
- It still type-checks (`npm run typecheck`), so it stays usable as a reference.
