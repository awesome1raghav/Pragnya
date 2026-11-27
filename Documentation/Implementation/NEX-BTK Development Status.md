# NEX-BTK development status

NEX-BTK is an extension proposed in `C:\Users\ragha\Downloads\Untitled document.md`. The approved canonical investigation flowchart still defines 18 modules and 12 directly coordinated T-MIR modules. This extension has **not** been inserted into that graph or declared a T-MIR engine. Its supplemental ownership and relationships are defined in `NEX-BTK Architecture Addendum.md`.

## First verified slice: local video comparison

- Reuses NEX-FPM's one-frame-per-second pHash/dHash fingerprints and the existing controlled, self-generated QA corpus. The comparison checks temporal offset and one-to-one monotonic frame ordering, then reports matched frame pairs, merged sampled intervals, and coverage for each video.
- `POST /api/v1/cases/{case_id}/backtracking/compare` compares two preserved videos in the same case. It verifies both original-file SHA-256 hashes before decoding. It does not acquire media or modify originals.
- Flat footage or insufficient distinct frames returns `INCONCLUSIVE` with null coverage. A candidate match is evidence of shared sampled visual content, not proof of origin or direction. The separate `/verify` endpoint adds audio and bounded geometric checks.

## Controlled results, 2026-11-27

`Tests/QA-Audit/NEXTRON-QA-001` was used with the isolated `nextron_e2e` database and `tmp/e2e-storage`:

| Comparison | API result | Matched frames | Submitted coverage | Candidate coverage | Offset |
| --- | --- | ---: | ---: | ---: | ---: |
| VID-01 / resized VID-02 | CANDIDATE_MATCH | 12 | 100% | 100% | 0 s |
| VID-01 / trimmed VID-03 | CANDIDATE_MATCH | 10 | 83.33% | 100% | -2 s |
| VID-01 / flat VID-04 | INCONCLUSIVE | 0 | unavailable | unavailable | unavailable |

`.venv\Scripts\python.exe -m pytest Tests/Integration/Engines/test_btk_video_slice.py -q` returned `2 passed`.

## Implementation stages

1. **Implemented and tested:** indexed case inventory and append-only, versioned comparisons (`0011`).
2. **Implemented and tested:** bounded expansion jobs with lease recovery, retries, cancellation, and checkpointed frontier (`0012`).
3. **Implemented and tested:** NEX-SRC occurrence views keep URL outcomes separate from preserved media. Inaccessible sources remain metadata only.
4. **Implemented and tested on controlled media:** image resize, center crop, mirror and rotation hypotheses; audio sub-fingerprints; sampled video timing, speed hypotheses and geometric checks. Each check reports a candidate, no verified local match, or inconclusive. NEX-INV reviews comparison IDs separately (`0013`).
5. **Implemented:** case Backtracking tab, candidate graph, pair coverage, source occurrences, history, media verification, and evidence inspector. Comparison IDs link to original evidence and reviews.
6. **Validated on controlled data:** media positives and negatives, a known half-speed transform, 100-comparison budget rejection, case scope, metadata-only sources, expired-lease recovery, duplicate prevention, migrations, and JSON/PDF report traceability. Frontend typecheck and production build pass.

NEX-BTK still does **not** perform recursive URL discovery, internet-wide search, automatic provenance determination, or independent report generation. Its geometric checks cover bounded center crops, mirror, and rotations; broader transforms and field false-positive calibration remain future research.
