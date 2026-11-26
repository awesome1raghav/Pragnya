# `pragnya.md` checked against the current build (27 November 2026)

`C:\Users\ragha\Downloads\PRagnya\pragnya.md` asks for datasets, pretrained models, a backtracking engine, evaluation
and a Research Lab on top of NEXTRON (this repository, `awesome1raghav/Pragnya`). This compares each request with
what exists and was measured. Nothing was changed to produce it.

## Its premises are out of date

| The file says | Measured or built |
|---|---|
| NEX-SRC … NEX-RPT not implemented | All 18 modules exist: 8 IMPLEMENTED, 10 PARTIAL, 0 NOT_IMPLEMENTED (`/system/modules`) |
| 16 GB RAM, under 50 GB free | 23.3 GB RAM; 658.6 GB free on C:. GPU: RTX 5050 Laptop, 8 GB, driver 592.82 (Blackwell: needs CUDA 12.8+ wheels; detectors run on CPU today) |
| OpenCV in the stack | Not used; Pillow, NumPy and FFmpeg do the image and video work |

## Already done, with evidence

| Request | Where |
|---|---|
| Pretrained models first, pinned and isolated | `Backend/App/Detectors` (SHA-256 manifest, `weights_only`, separate host process); [Detector Benchmark](../Testing/Detector%20Benchmark.md) |
| Image model with real inference | Community Forensics ViT-S (synthetic images): AUC 0.997 on its evaluation set. Note: detection, not localisation |
| AASIST family for speech | SSL-AASIST (DF): AUC 0.966, EER 8.0 % on In-the-Wild. Not the plain `clovaai/aasist` checkpoint |
| Fingerprints: SHA-256, pHash, dHash, frame fingerprints, audio sub-fingerprints, Chromaprint optional | NEX-FPM; controlled set precision 1.00, recall 0.91 |
| Lineage, never direction from similarity | NEX-MOC: every relationship stays CANDIDATE; "earlier observed" only from sources' claimed times |
| Alignment, transformation, cross-modal correlation | NEX-ALN (video ±0.5 s, audio ±0.05 s), NEX-TRN (trim, speed, audio replaced, crop, resize, re-encode), NEX-CMC |
| Graph, timeline, review, report | NEX-EGC, NEX-REC, NEX-INV, NEX-RPT (JSON + PDF + SHA-256, FINAL only after a reviewed conclusion) |
| T-MIR: dependencies, executors, states, timeouts, retries, reproducibility | Steps 2–3; MODULE_NOT_IMPLEMENTED / UNAVAILABLE reported honestly |
| Acceptance B, C, D, F, H, I, J | Shown by `test_engines`, `test_sources_lineage`, `test_correlation` (offsets, trims, AUDIO_REPLACED), `test_investigation`, and the Step 7–9 browser tests |

## Gaps

| # | Request | State | Size of the work |
|---|---|---|---|
| 1 | Machine-readable dataset registry (`Datasets/registry`, licences, checksums, manifests, validation) | Missing. `Datasets/` holds empty placeholder folders; the two evaluation sets used (`Benchmarks/Data`) are described only in prose | Small |
| 2 | Persisted controlled corpus with `lineage.json`, `assets.json`, `transformations.json`, source-group splits | The controlled sets are generated inside tests and thrown away | Medium |
| 3 | Official C2PA public test files (acceptance G) | NEX-PRV is tested with signed fixtures made here, not the official files | Small |
| 4 | PDQ; ORB/SIFT with RANSAC geometric verification | Missing. Would raise the 71 % recall on 10 % crops | Medium |
| 5 | Video alignment by sequence alignment; missing-frame detection | Line fit on frame matches; dropped frames not reported as such | Medium |
| 6 | Relationship vocabulary (EXACT_DUPLICATE, PERCEPTUAL_MATCH, PARTIAL_COPY, POSSIBLE_DERIVATIVE, SHARED_SCENE, UNKNOWN) | Ours: NEAR_DUPLICATE, SAME_CONTENT_VARIANT, FRAME_OF_VIDEO, SHARED_VIDEO_SEGMENT, SHARED_AUDIO; exact duplicates flagged at upload. A mapping, not missing function | Small |
| 7 | TruFor (manipulation localisation) | Not integrated. Licence and checkpoint terms must be read first | Medium |
| 8 | DeepfakeBench face-video detector | GenD pinned, not evaluated: needs a licensed face-swap test set (FaceForensics++ requires an access request) | Blocked on access |
| 9 | FIVR-200K/PVCD annotations, DISC21 subset, GenImage subset, ASVspoof 2021 subset | None acquired. DISC21 needs Meta's agreement; ASVspoof needs registration | Access and downloads |
| 10 | Research Lab page and API (dataset and model registry, run history, measured status only) | Missing; `/system/modules` and the benchmark documents cover part of it | Medium |
| 11 | Report: chain of custody, model and dataset versions, HTML (Jinja2) | Report has evidence hashes and findings; custody events, tool versions and HTML are missing | Small |
| 12 | Metrics: Recall@K / mAP, temporal IoU, macro-F1 | Only AUC/EER (detectors) and precision/recall (fingerprints) measured | Medium, after 2 |
| 13 | Training or fine-tuning | None, and none justified yet: no adequate labelled data | Decision recorded here |
| 14 | `ML/` folder layout | Equivalent pieces live in `Backend/App/Detectors`, `Backend/Models` (git-ignored), `Benchmarks/`. Moving them buys nothing | Not recommended |

## Suggested order if this is taken on

1. Gaps 1, 2, 3, 11: registry, persisted controlled corpus, official C2PA files, report completeness. No access requests.
2. Gaps 4, 5, 6, 12: PDQ and local-feature verification, sequence alignment and dropped frames, vocabulary mapping, retrieval and alignment metrics on the corpus from step 1.
3. Gaps 10 and 7: Research Lab from the registry and measured runs; TruFor once its licence is checked.
4. Gaps 8 and 9: only after you request access to FaceForensics++, DISC21 and ASVspoof.
