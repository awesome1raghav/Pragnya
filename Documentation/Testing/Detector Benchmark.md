# Detector Benchmark

26 November 2026. The shortlist from [Detector Candidates](../Research/Detector%20Candidates.md), measured on this
machine: Windows 11, AMD Ryzen 7 260 (8 threads), 23 GB RAM, **CPU only**. Code:
`Benchmarks/Detectors/RunBenchmark.py`; every item's score, label and time is in `Benchmarks/Results/*.json`, so each
number below can be recomputed. Weights are pinned by SHA-256 (`Backend/App/Detectors/Manifest.py`) and were loaded
with PyTorch's restricted loader (tensors and plain data only; no code from the files runs).

## Results

### Images: 500 images from CommunityForensics-Eval (4 of 413 shards)

212 fakes (DFGAN 122, GALIP 90) and 288 real (RAISE camera photos 161, ImageNet 124, COCO 3).

| Detector | ROC AUC | EER | At its 0.5 threshold: real flagged / fakes caught | TPR at 1 % FPR | Median s/image | Peak RAM |
|---|---:|---:|---|---:|---:|---:|
| **Community Forensics** (ViT-S/16, 384) | **0.997** | **2.6 %** | 4.5 % / 98.6 % (RAISE camera photos: 8.1 % flagged) | **97.6 %** | **0.17** | **0.6 GB** |
| SPAI (stopped at 130 of 500) | — | — | DFGAN fakes caught: 60 of 122 (49 %); real flagged: 0 of 8 | — | 3.0 (small images); **230 per 16-MP camera photo** | 3.5 GB |

### Speech: 800 clips from In-the-Wild (400 deepfake, 400 bona fide; 49 public figures)

| Detector | ROC AUC | EER | At its 0.5 threshold: real flagged / fakes caught | TPR at 1 % FPR | Median s/clip | Peak RAM |
|---|---:|---:|---|---:|---:|---:|
| **SSL-AASIST, DF model** | **0.966** | **8.0 %** | 63 % / 100 % | 40 % | **0.66** | **2.9 GB** |
| SSL-AASIST, LA model | 0.955 | 11.0 % | 56 % / 99.5 % | 63 % | 0.72 | 3.1 GB |

Calibration (Platt scaling fitted on half A, measured on half B, split by a stable hash): DF expected calibration
error 0.31 raw → 0.05 calibrated, accuracy at 0.5 after calibration 88 %; LA 0.29 → 0.05, 90 %.

### Face-manipulation video

**Not benchmarked.** GenD (MIT) is downloaded and pinned and loads under the restricted loader, but no licensed
face-swap test set is available here: Celeb-DF and FaceForensics++ need a signed access request. Running it would also
need a face detector and the `lightning` and `peft` packages, which are not installed.

SPAI's run was stopped after 130 images (scores kept in `Benchmarks/Results/SPAI-partial-130-of-500.jsonl`): it
scores every 224-pixel patch at the original resolution, so a 16-megapixel camera photo took about 230 s on this CPU
and the remaining RAISE photos alone would have taken about ten hours. That cost rules it out for CPU deployment
regardless of accuracy; it stays pinned and selectable (`IMAGE_DETECTOR=Spai`) for machines with a GPU.

## What the numbers mean (and do not)

- **Community Forensics is excellent on this set, and this set flatters it.** It is the authors' own evaluation data,
  and every fake here is from a GAN; no diffusion model or recent commercial generator is included. Independent
  zero-shot studies put open detectors at 18–30 % on Flux, Firefly and Midjourney v7. Real camera photos (RAISE,
  high-resolution TIFF) are flagged more often (8 %) than web images.
- **SSL-AASIST ranks well but its own threshold is unusable on real-world speech**: at 0.5 it flags most genuine
  clips (scores saturate near 1). NEXTRON therefore compares its score with the equal-error-rate threshold measured
  here (0.99970943: 8.5 % of real clips flagged, 92.5 % of fakes caught) and says so in every finding. Because the
  scores are saturated, small processing differences can move a clip across that threshold.
- **False alarms cluster on archival recordings**: at that threshold 4 of 15 Martin Luther King and 3 of 13 Winston
  Churchill clips were flagged; Bill Clinton deepfakes were missed most (7 of 19). Recording age and quality matter.
- **No result is a calibrated probability for NEXTRON's media.** Platt scaling fitted here only describes this
  dataset; NEXTRON reports the raw score (METHOD_SPECIFIC), the threshold and its source, and keeps confidence null.
- Timing excludes one interval during which the computer slept (one clip "took" 3,628 s); medians are reported. The
  first two runs' memory was measured afterwards (`MeasureMemory.py`, load + 20 items) because the original reading
  failed.

## Decision

| Modality | Chosen | Why | Setting |
|---|---|---|---|
| Images | **Community Forensics** | Caught 99 % of the GAN fakes SPAI caught 49 % of; about 1,300× faster on camera photos (0.17 s vs 230 s on CPU); 0.6 GB vs 3.5 GB; MIT | `IMAGE_DETECTOR=CommunityForensics` |
| Speech | **SSL-AASIST, DF model** | Higher AUC and lower EER than LA on real-world deepfakes; slightly faster and lighter | `SPEECH_DETECTOR=SSL-AASIST-DF` |
| Face video | none yet | Needs a licensed test set before any claim can be made | — |

How they run in NEXTRON: a separate detector process (`Backend/App/Detectors/Host.py`) loads each model once, answers
one request at a time, is killed and restarted on a hang or crash, and never downloads anything (offline mode).
NEX-IMG scores the whole image; NEX-AUD scores up to three 4-second windows (start, middle, end) and reports the
highest with its time range. Each score becomes a `SYNTHETIC_IMAGE_DETECTOR` or `SYNTHETIC_SPEECH_DETECTOR` finding:
assertion INFERENCE, score_kind METHOD_SPECIFIC, the threshold and its source, the training data and the figures
above as limitations. A missing, mismatched or failing detector leaves the module PARTIALLY_COMPLETED with
`DETECTOR_NOT_INSTALLED`, `DETECTOR_FAILED` or `DETECTOR_DISABLED`, never a guessed result.

## Data used

| Set | Licence | Used | Notes |
|---|---|---|---|
| CommunityForensics-Eval | CC BY-NC-SA 4.0 | 4 shards, 500 images | Internal evaluation only. Shards vary from 5 MB to 2.7 GB; 3.5 GB was downloaded against an estimate of 0.14 GB |
| In-the-Wild (Müller et al., 2022) | CC BY-SA 4.0 | 800 of 31,779 clips, seed 20261126 | 7.6 GB archive |
