# Detector Candidates: comparison before integration

26 November 2026. Desk comparison only: nothing was downloaded or run. Licences and weight locations were read from
each repository and Hugging Face (file listings via the Hub API); accuracy figures are the authors' or third-party
benchmark numbers, not NEXTRON measurements. The archive (§4, §16) requires this comparison before a detector is
chosen: accuracy, CPU latency, memory, licence, checkpoint provenance, reproducibility, out-of-distribution robustness.

## What the field reports (read this first)

- **No detector generalises well to what circulates today.** Zero-shot, 16 open image detectors (23 checkpoints) on
  2.6 M images from 291 generators: best 75 % mean accuracy, worst 37.5 %, rankings unstable; recent commercial
  generators (Flux Dev, Firefly v4, Midjourney v7) bring most detectors down to 18–30 % ([Ren et al. 2026][oob]).
- **Video:** on deepfakes that actually circulated in 2024, open-source video detectors lose about half their academic
  AUC; the best open models score AUC ≈ 0.56–0.63 ([Deepfake-Eval-2024][de24]; [2026 follow-up][evolving]).
- **Audio:** a strong public checkpoint (wav2vec2-AASIST) goes from 4.7 % to 18.2 % EER when audio is simply replayed
  through a speaker ([Replay attacks][replay]).

Consequence for NEXTRON: a detector is **one signal**, recorded as an INFERENCE with a METHOD_SPECIFIC score and its
training scope stated; confidence stays null unless we calibrate on held-out data ourselves. It never becomes a verdict.

## Candidates

### Images (NEX-IMG; also usable on sampled video frames for fully generated video)

| Candidate | Weights licence | Weights (where, size, format) | Trained on | Reported generalisation | Verdict |
|---|---|---|---|---|---|
| **Community Forensics** (Park & Owens, CVPR 2025) | MIT | HF `OwensLab/commfor-model-384`, **83 MB, safetensors** (no code runs on load) | 4,800+ generators (dataset 1.1 TB) | Designed for unseen generators; no single README figure | **Shortlist #1**: licence, size, safe format, breadth of training |
| **SPAI** (Karageorgiou et al., CVPR 2025) | Apache-2.0 (code and weights) | Google Drive, size not stated | Latent-diffusion fakes + COCO/LSUN | Any-resolution spectral method; no README figure | **Shortlist #2**: complementary (spectral, no resizing) |
| UniversalFakeDetect (Ojha et al., CVPR 2023) | MIT | In repo (linear head) + CLIP ViT-L/14 (≈ 0.9 GB) | ProGAN | AIDE-era tables put ProGAN-trained probes ≈ 73 % average ([CVPR 2026][proto]) | Baseline only: old training data |
| B-Free (Guillaro et al., CVPR 2025) | **"informational and nonprofit purposes" only** | Not linked in README | SD 2.1 self-conditioned + COCO | Strong in the paper | **Excluded** unless NEXTRON is strictly non-profit |
| NPR (Tan et al., CVPR 2024) | **No licence** | In repo | ProGAN 4-class | 91.7 % on AIGCDetectBenchmark | **Excluded**: no licence means no right to use |

### Face-manipulation video (NEX-VID)

| Candidate | Weights licence | Weights | Trained on | Reported generalisation | Verdict |
|---|---|---|---|---|---|
| **GenD** (Yermakov et al., WACV 2026) | MIT | HF `yermandy/deepfake-detection`: `model.ckpt` 1.16 GB (pickle) or `model.torchscript` 579 MB, **flagged "Suspicious" by the Hub scan** | FF++ | Best average cross-dataset AUROC in its WACV 2026 evaluation | **Shortlist**, loaded only in an isolated process (below) |
| GenConViT | **CC BY-NC 4.0** on the weights (code MIT) | HF, 3.0 GB | DFDC, FF++, TIMIT, Celeb-DF | AUC 0.63 on Deepfake-Eval-2024 | **Excluded** for licence and size |
| DeepfakeBench zoo (36 detectors) | **CC BY-NC 4.0** | GitHub releases | FF++ c23 | Frame-level cross-dataset tables | Excluded for licence; useful as a reference protocol |

Face detectors need face crops: GenD uses DeepfakeBench preprocessing (dlib landmarks), so integrating it also
means choosing a face detector with a usable licence.

### Synthetic speech (NEX-AUD)

| Candidate | Licence | Weights | Trained on | Reported | Verdict |
|---|---|---|---|---|---|
| **SSL-AASIST** (Tak et al.) | MIT (code); XLS-R base Apache-2.0 | Google Drive (LA and DF models, size not stated) + `facebook/wav2vec2-xls-r-300m` **1.21 GB** | ASVspoof 2019 LA | EER 0.82 % (2021 LA), 2.85 % (2021 DF); in-the-wild much worse | **Shortlist** |
| AASIST / AASIST-L (Jung et al.) | MIT | README says provided; no file or link found | ASVspoof 2019 LA | EER 0.83 % / 0.99 % (2019 LA); 85 k params (L) | Only if weights are found; narrow training |

## How a chosen detector would be integrated

- **Pinned and verified:** exact file, SHA-256 and source recorded in the repository; the worker refuses a file whose
  hash differs. Model and version go into the input fingerprint, so a model change re-runs analysis.
- **Untrusted formats stay out of the API:** safetensors is preferred. Pickle or TorchScript weights (GenD,
  SSL-AASIST) run only in a separate detector subprocess with no network and a timeout, never inside the API or worker
  process that holds database connections.
- **Honest output:** finding `SYNTHETIC_IMAGE_DETECTOR` (or `…_VIDEO`, `…_SPEECH`), assertion INFERENCE,
  score_kind METHOD_SPECIFIC, the model's training scope and the benchmark figures above as limitations. Confidence only
  as CALIBRATED_PROBABILITY after calibration on our held-out split, with the basis stated.
- **CPU first:** PyTorch CPU wheel; GPU used when present (archive: GPU availability unknown).

## Benchmark plan (needs your approval to download)

Measured locally on CPU, per candidate: ROC AUC, accuracy at the threshold chosen on a calibration split, expected
calibration error, false-positive rate on real media, seconds per item, peak memory. Results go in
`Documentation/Testing/Detector Benchmark.md`, then one detector per modality is chosen.

| Modality | Evaluation data | Licence | Size | Caveat |
|---|---|---|---|---|
| Images | CommunityForensics-Eval, 10 of 413 shards | CC BY-NC-SA 4.0 (internal evaluation only) | ≈ 140 MB | Favourable to Community Forensics (same authors); a second, independent set is needed (see below) |
| Images (independent) | Real photos and fakes NEXTRON's team makes or collects with clear rights | Ours | small | Best test of what NEXTRON will actually see |
| Speech | In-the-Wild (Müller et al.) | CC BY-SA 4.0 | 7.6 GB (one zip) | Real-world celebrity/politician deepfakes |
| Face video | Celeb-DF v2 or FF++ | Access by signed request form | — | Needs you to request access; GenD is benchmarked on FF++-family data already |

Downloads this would need (all from the sources above): PyTorch CPU + safetensors + timm (PyPI, ≈ 250 MB);
Community Forensics 83 MB; SPAI (size unknown, Google Drive); GenD `model.ckpt` 1.16 GB; XLS-R 300M 1.21 GB;
SSL-AASIST checkpoint (size unknown, Google Drive); evaluation data ≈ 7.7 GB. About 10.5 GB in total.

[oob]: https://arxiv.org/abs/2602.07814
[de24]: https://arxiv.org/pdf/2503.02857
[evolving]: https://arxiv.org/html/2607.13234v1
[replay]: https://arxiv.org/html/2505.14862v2
[proto]: https://openaccess.thecvf.com/content/CVPR2026/papers/Qin_Scaling_Up_AI-Generated_Image_Detection_with_Generator-Aware_Prototypes_CVPR_2026_paper.pdf

Repositories read: [UniversalFakeDetect](https://github.com/WisconsinAIVision/UniversalFakeDetect),
[NPR](https://github.com/chuangchuangtan/NPR-DeepfakeDetection), [B-Free](https://github.com/grip-unina/B-Free),
[SPAI](https://github.com/mever-team/spai), [Community Forensics](https://github.com/JeongsooP/Community-Forensics),
[DeepfakeBench](https://github.com/SCLBD/DeepfakeBench), [GenD](https://github.com/yermandy/deepfake-detection),
[GenConViT](https://github.com/erprogs/GenConViT), [AASIST](https://github.com/clovaai/aasist),
[SSL_Anti-spoofing](https://github.com/TakHemlata/SSL_Anti-spoofing), [GenD weights](https://huggingface.co/yermandy/deepfake-detection),
[GenConViT weights](https://huggingface.co/Deressa/GenConViT), [CommunityForensics-Eval](https://huggingface.co/datasets/OwensLab/CommunityForensics-Eval).
