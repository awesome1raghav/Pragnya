# NEX-BTK architecture addendum

NEX-BTK is a supplemental, case-scoped investigation service. It is not a nineteenth canonical module or a T-MIR engine. The approved 18-module graph and its 12 coordinated T-MIR modules remain unchanged.

## Ownership and boundaries

- The NEX-BTK API owns local candidate inventory, manual verification, saved comparison history, coverage, and a separate candidate graph view.
- The Job Service owns state, leases, retries, cancellation, and outbox events for `BACKTRACK_EXPANSION`. The NEX-BTK worker owns the bounded frontier and checkpoints it with each comparison.
- NEX-FPM supplies versioned perceptual and audio fingerprints. NEX-BTK verifies preserved originals before using them; it does not modify evidence or acquire media.
- NEX-SRC owns URL retrieval and source observations. NEX-BTK reads those records only. Each source occurrence remains distinct from a preserved evidence asset. Unavailable sources are metadata only.
- NEX-INV owns append-only investigator decisions on comparison IDs. NEX-RPT includes those decisions and the comparison's hashes and algorithm versions in report artifacts. No candidate match is automatically accepted as lineage or direction.

## Data and safety

`backtracking_comparisons` is append-only and unique on case, ordered evidence IDs, input hashes, and algorithm versions. A saved record is current only while both hashes and algorithm versions match. Investigation graph edges are candidates from saved records; review decisions are separate records. Search is limited to 100 local videos and 100 comparisons per run.

The service performs no internet-wide search, recursive URL discovery, automatic provenance determination, or independent report generation.
