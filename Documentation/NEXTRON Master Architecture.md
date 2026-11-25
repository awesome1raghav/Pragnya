# NEXTRON — Master System Architecture

**Intelligent Deepfake & Digital Media Verification System**  
Version 1.0 · Proposed architecture baseline

10 layers · 33 logical modules · 3 forensic branches · 2 connected pipelines

## 1. Complete system architecture

```mermaid
flowchart TB
 USER[User / Investigator] --> UI[User Interface: Upload, Dashboard, Evidence Viewer, Reports]
 subgraph L1[Layer 1 — Application and Orchestration]
 API[API Gateway]
 AUTH[Access Control]
 JOB[Job Orchestrator: Workflow, State, Retry, Timeout]
 end
 subgraph L2[Layer 2 — Media Ingestion]
 INPUT[Media Input]
 VALID[Media Validation: Format, Codec, Duration, Integrity]
 META[Metadata and Provenance Analyzer]
 end
 subgraph L3[Layer 3 — Media Processing]
 DECODER[Video Decoder: Frames, PTS, Frame Index]
 SCENE[Scene and Frame Processor]
 FACE[Face Detection and Tracking]
 AUDIO[Audio Extractor: Segmentation and Alignment]
 end
 subgraph L4[Layer 4 — Forensic Intelligence]
 SPATIAL[Spatial Detection Engine]
 REGION[Region Localization Engine]
 TEMPORAL[Temporal Detection Engine]
 TLOC[Temporal Localization Engine]
 AV[Audio-Visual Consistency Engine]
 end
 subgraph L5[Layer 5 — Evidence Intelligence]
 NORMAL[Evidence Normalization Engine]
 FUSION[Evidence Fusion Engine]
 UNCERTAINTY[Uncertainty and Decision Engine]
 end
 subgraph L6[Layer 6 — Classification and Reporting]
 CLASS[Manipulation Classification Engine]
 VIS[Evidence Visualization Engine]
 REPORT[Forensic Report Generator]
 end
 subgraph L7[Layer 7 — Data and Model Management]
 DATAREG[Dataset Registry]
 MODELREG[Model Registry]
 LIFECYCLE[Model Lifecycle Manager: Train, Evaluate, Approve, Deploy]
 end
 subgraph L8[Layer 8 — Evaluation and Monitoring]
 BENCH[Benchmark Evaluation Engine]
 ROBUST[Robustness Testing Engine]
 MONITOR[Performance Monitoring]
 end
 subgraph L9[Layer 9 — Infrastructure]
 DB[(Relational Database)]
 STORAGE[(Media and Artifact Storage)]
 QUEUE[Task Queue Manager]
 OBS[Observability and Logging]
 end
 subgraph L10[Layer 10 — Security and Governance]
 INTEGRITY[Evidence Integrity Manager: Hashes, Audit, Chain of Custody]
 PRIVACY[Privacy and Retention Manager]
 end
 UI <--> API
 API --> AUTH --> JOB
 API --> INPUT --> VALID
 VALID -->|Valid| META --> JOB
 VALID -->|Invalid| API
 JOB --> QUEUE --> DECODER
 DECODER --> SCENE --> FACE
 DECODER --> AUDIO
 SCENE --> SPATIAL
 FACE --> SPATIAL
 FACE --> REGION
 SCENE --> TEMPORAL
 FACE --> TEMPORAL --> TLOC
 AUDIO --> AV
 FACE --> AV
 SCENE --> AV
 META -. Supporting evidence .-> NORMAL
 SPATIAL --> NORMAL
 REGION --> NORMAL
 TEMPORAL --> NORMAL
 TLOC --> NORMAL
 AV --> NORMAL --> FUSION --> UNCERTAINTY --> CLASS --> VIS --> REPORT --> UI
 DATAREG -.-> LIFECYCLE
 MODELREG -.-> LIFECYCLE
 LIFECYCLE -.-> SPATIAL
 LIFECYCLE -.-> TEMPORAL
 LIFECYCLE -.-> AV
 SPATIAL -.-> BENCH
 TEMPORAL -.-> BENCH
 AV -.-> BENCH
 BENCH --> ROBUST --> MODELREG
 JOB <--> DB
 NORMAL --> DB
 REPORT --> STORAGE
 INPUT --> STORAGE
 DECODER --> STORAGE
 QUEUE --> MONITOR --> OBS
 JOB --> OBS
 INPUT --> INTEGRITY --> DB
 PRIVACY --> STORAGE
 PRIVACY --> DB
```

Dotted arrows represent supporting information, governance or evaluation relationships, not necessarily runtime calls. The original baseline's stated 33-module count should be reconciled with the 32 explicitly named layer modules plus the UI; this document treats the UI as the 33rd component.

## 2. Complete video verification workflow

```mermaid
flowchart TD
 A[User uploads video] --> B[Generate verification Job ID] --> C[Calculate SHA-256 hash] --> D[Store original video as immutable input] --> E[Validate file]
 E --> F{Is media valid?}
 F -->|No| REJECT[Rejected: Return validation error]
 F -->|Yes| G[Extract metadata and provenance signals] --> H[Create job record] --> I[Queue verification task] --> J[Decode video]
 J --> K[Extract timestamped frames] --> M[Scene segmentation] --> N[Frame sampling] --> O[Face detection and tracking]
 J --> L[Extract audio stream]
 N --> P[Spatial analysis]
 O --> P --> P1[Frame-level detection] --> P2[Region localization]
 N --> T[Temporal analysis]
 O --> T --> T1[Sequence feature extraction] --> T2[Temporal classification] --> T3[Suspicious segment localization]
 L --> AV{Usable audio available?}
 O --> AV
 AV -->|Yes| AV1[Audio-visual analysis] --> AV2[Speech and lip-motion alignment] --> AV3[Synchronization evidence]
 AV -->|No| AV4[Branch marked unavailable]
 P2 --> EVIDENCE[Collect branch evidence]
 T3 --> EVIDENCE
 AV3 --> EVIDENCE
 AV4 --> EVIDENCE
 G --> EVIDENCE
 EVIDENCE --> NORMAL[Normalize evidence] --> FUSION[Correlate and fuse evidence] --> DECISION[Estimate uncertainty] --> RESULT{Enough valid evidence?}
 RESULT -->|No| INC[Inconclusive]
 RESULT -->|Yes| CLASS[Classify manipulation evidence]
 CLASS --> VIS[Build evidence timeline and visualizations]
 INC --> VIS
 VIS --> REPORT[Generate forensic report] --> HASH[Hash report and evidence artifacts] --> SAVE[Save results and audit trail] --> COMPLETE[Job completed] --> UI[Display results to user]
```

| Category | What NEXTRON investigates |
|---|---|
| Fully AI-generated | Entire video generated synthetically |
| Face swap | One person's face replaced with another |
| Facial reenactment | Facial expressions or movements manipulated |
| Lip-sync manipulation | Visible speech does not match audio |
| Partial manipulation | Selected frames or regions altered |
| Inconclusive | Insufficient or conflicting evidence |

Mixed cases must also be supported, including authentic footage with manipulated sections.

## 3. ML training and research architecture

Training is separate from normal video verification. Training creates model versions; inference consumes approved versions.

```mermaid
flowchart TB
 subgraph RESEARCH[Research and Data Acquisition]
 PAPER[Research Papers]
 DATASET[Public Deepfake Datasets]
 SOURCES[Dataset Sources and Access]
 AUDIT[Dataset License and Annotation Audit]
 MANIFEST[Dataset Manifests]
 end
 PAPER --> AUDIT
 DATASET --> SOURCES --> AUDIT --> MANIFEST
 subgraph PREP[Data Preparation]
 VALIDATE[Dataset Validation]
 SPLIT[Train / Validation / Test Splits]
 DECODE[Media Decoding]
 EXTRACT[Frame and Audio Extraction]
 ANNOTATE[Label and Annotation Mapping]
 AUGMENT[Training Augmentation]
 end
 MANIFEST --> VALIDATE --> SPLIT --> DECODE --> EXTRACT --> ANNOTATE --> AUGMENT
 subgraph TRAINING[Independent Model Training Tracks]
 S[Spatial Training: Image and Region Models]
 T[Temporal Training: Sequence and Video Models]
 AV[Audio-Visual Training: Synchronization Models]
 F[Fusion Training: Evidence Integration]
 end
 AUGMENT --> S --> SE[Spatial Evaluation]
 AUGMENT --> T --> TE[Temporal Evaluation]
 AUGMENT --> AV --> AE[Audio-Visual Evaluation]
 SE --> CROSS[Cross-Dataset Evaluation]
 TE --> CROSS
 AE --> CROSS
 CROSS --> ROBUST[Robustness Evaluation] --> CAL[Calibration and Threshold Selection]
 SE --> EXP[Experiment Tracking]
 TE --> EXP
 AE --> EXP
 CAL --> EXP --> REVIEW{Meets acceptance criteria?}
 REVIEW -->|No| IMPROVE[Analyze Failure Cases]
 IMPROVE --> S
 IMPROVE --> T
 IMPROVE --> AV
 REVIEW -->|Yes| F --> FE[Fusion Evaluation] --> APPROVAL{Model review and approval}
 APPROVAL -->|Rejected| IMPROVE
 APPROVAL -->|Approved| REG[Model Registry] --> VERSION[Versioned Model Artifacts] --> DEPLOY[Inference Deployment]
 DEPLOY --> SP[Spatial Inference]
 DEPLOY --> TP[Temporal Inference]
 DEPLOY --> AP[Audio-Visual Inference]
```

### 3.1 ML tracks and inputs/outputs

| Track | Input | Expected output |
|---|---|---|
| Spatial | Video frames and regions | Visual manipulation evidence |
| Temporal | Ordered frame sequences | Temporal inconsistency and suspicious segments |
| Audio-visual | Audio and corresponding video segments | Synchronization evidence |
| Fusion | Standardized evidence from branches | Combined assessment |

### 3.2 Candidate datasets

- FaceForensics++ — manipulated facial videos.
- Celeb-DF — face manipulation research.
- DFDC — large-scale deepfake detection.
- DeeperForensics-1.0 — robustness evaluation.
- FakeAVCeleb — audio-visual manipulation.
- Deepfake-Eval-2024 — real-world generalization evaluation.

These are candidates, not final selections. Audit licensing, label quality, annotation granularity and task suitability. Keep test data separate from training, calibration and threshold selection.

## 4. Repository and GitHub architecture

```mermaid
flowchart TD
 ROOT[NEXTRON MONOREPO]
 ROOT --> DOCS[docs/]
 ROOT --> RESEARCH[research/]
 ROOT --> DATA[data/]
 ROOT --> TRAIN[training/]
 ROOT --> SRC[src/nextron/]
 ROOT --> MODELS[models/]
 ROOT --> FRONT[frontend/]
 ROOT --> TESTS[tests/]
 ROOT --> SCRIPTS[scripts/]
 ROOT --> DEPLOY[deployment/]
 ROOT --> GITHUB[.github/workflows/]
 DOCS --> D1[architecture/] & D2[research/] & D3[decisions/]
 RESEARCH --> R1[notebooks/] & R2[experiments/] & R3[baselines/] & R4[paper_reproductions/] & R5[findings/]
 DATA --> DA1[manifests/] & DA2[splits/] & DA3[schemas/]
 TRAIN --> TR1[spatial/] & TR2[temporal/] & TR3[audio_visual/] & TR4[fusion/] & TR5[common/]
 SRC --> S1[api/] & S2[orchestration/] & S3[ingestion/] & S4[validation/] & S5[preprocessing/] & S6[spatial/] & S7[temporal/] & S8[audio_visual/] & S9[evidence/] & S10[classification/] & S11[localization/] & S12[reporting/] & S13[storage/] & S14[security/] & S15[common/]
 MODELS --> M1[registry/] & M2[configs/]
 TESTS --> T1[unit/] & T2[integration/] & T3[contract/] & T4[end_to_end/] & T5[robustness/]
 SCRIPTS --> SC1[prepare_dataset.py] & SC2[validate_dataset.py] & SC3[run_training.py] & SC4[benchmark.py]
 DEPLOY --> DP1[Dockerfile] & DP2[compose.yaml]
 GITHUB --> CI1[tests.yml] & CI2[lint.yml] & CI3[security.yml]
```

| Directory | Responsibility | GitHub? |
|---|---|---|
| `docs/` | Architecture and research documentation | Yes |
| `research/` | Notebooks, experiments and findings | Yes, excluding large outputs |
| `data/` | Manifests, splits and schemas | Yes |
| `training/` | Model training code | Yes |
| `src/` | Application and inference source code | Yes |
| `models/` | Model configuration and registry metadata | Yes |
| `frontend/` | User-facing application | Yes |
| `tests/` | Automated testing | Yes |
| `deployment/` | Container and deployment configuration | Yes |
| Raw datasets | Actual video/audio files | Separate storage |
| Model checkpoints | Large trained model artifacts | Separate artifact storage |

## 5. Internal module dependency architecture

```mermaid
flowchart LR
 subgraph APP[Application]
 UI[Frontend]
 API[API Gateway]
 ORCH[Job Orchestrator]
 end
 subgraph INGEST[Ingestion]
 INPUT[Media Input]
 VALID[Media Validation]
 META[Metadata Analyzer]
 end
 subgraph PROCESS[Processing]
 DEC[Video Decoder]
 FRAME[Frame Processor]
 FACE[Face Tracking]
 AUD[Audio Extractor]
 end
 subgraph INTEL[Forensic Engines]
 SP[Spatial Engine]
 REG[Region Localization]
 TMP[Temporal Engine]
 TLOC[Temporal Localization]
 AV[Audio-Visual Engine]
 end
 subgraph EVIDENCE[Evidence]
 NORM[Evidence Normalization]
 FUS[Evidence Fusion]
 UNC[Uncertainty Engine]
 CLS[Classification]
 end
 subgraph OUTPUT[Output]
 VIS[Evidence Visualization]
 REP[Report Generator]
 end
 subgraph PLATFORM[Shared Platform]
 DB[Database]
 STORE[Storage]
 QUEUE[Task Queue]
 MODEL[Model Registry]
 LOG[Observability]
 SEC[Security and Integrity]
 end
 UI <--> API --> ORCH --> INPUT --> VALID --> META --> DEC
 API --> SEC
 DEC --> FRAME --> FACE
 DEC --> AUD
 FRAME --> SP
 FACE --> SP
 FACE --> REG
 FRAME --> TMP
 FACE --> TMP --> TLOC
 AUD --> AV
 FACE --> AV
 SP --> NORM
 REG --> NORM
 TMP --> NORM
 TLOC --> NORM
 AV --> NORM
 META --> NORM
 NORM --> FUS --> UNC --> CLS --> VIS --> REP --> API
 ORCH <--> QUEUE
 ORCH <--> DB
 INPUT --> STORE
 FRAME --> STORE
 REP --> STORE
 NORM --> DB
 SP -.-> MODEL
 TMP -.-> MODEL
 AV -.-> MODEL
 ORCH --> LOG
 SEC --> DB
 SEC --> STORE
```

**Dependency rule:** Independent forensic branches publish findings through standardized contracts rather than calling one another directly. This avoids tight coupling and allows model replacement.

## 6. Evidence fusion and decision architecture

```mermaid
flowchart TD
 S[Spatial Evidence] --> N[Evidence Normalization]
 T[Temporal Evidence] --> N
 A[Audio-Visual Evidence] --> N
 M[Metadata and Provenance Signals] --> N
 N --> Q[Quality and Availability Check] --> CORR[Evidence Correlation Analysis] --> F[Evidence Fusion] --> CAL[Calibration and Uncertainty Estimation] --> D{Decision Policy}
 D --> AUTH[Evidence consistent with authentic content]
 D --> SYN[Evidence consistent with AI-generated content]
 D --> MAN[Evidence consistent with manipulated content]
 D --> MIX[Mixed or localized manipulation evidence]
 D --> INC[Inconclusive / Insufficient evidence]
 AUTH --> OUT[Assessment Record]
 SYN --> OUT
 MAN --> OUT
 MIX --> OUT
 INC --> OUT
 OUT --> TRACE[Trace to supporting findings, timestamps and model versions] --> REPORT[Forensic Report]
```

### Decision safeguards

- A missing branch is not a negative result.
- Multiple correlated models are not automatically independent evidence.
- A high raw model score is not automatically a calibrated probability.
- A video-level classification is not a localization result.
- A provenance signal cannot establish authenticity by itself.
- A conflicting result must be visible in the report.

## 7. Database architecture and entity relationships

```mermaid
erDiagram
 USERS ||--o{ VERIFICATION_JOBS : submits
 VERIFICATION_JOBS ||--o{ MEDIA_ASSETS : references
 VERIFICATION_JOBS ||--o{ JOB_EVENTS : records
 VERIFICATION_JOBS ||--o{ ANALYSIS_RUNS : contains
 ANALYSIS_RUNS }o--|| MODEL_VERSIONS : uses
 ANALYSIS_RUNS ||--o{ EVIDENCE_FINDINGS : produces
 VERIFICATION_JOBS ||--o| ASSESSMENTS : produces
 ASSESSMENTS ||--o| REPORTS : generates
 VERIFICATION_JOBS ||--o{ AUDIT_EVENTS : records
 DATASETS ||--o{ EXPERIMENTS : used_in
 EXPERIMENTS ||--o{ MODEL_VERSIONS : produces
 USERS {
 uuid user_id PK
 string email
 string role
 datetime created_at
 }
 VERIFICATION_JOBS {
 uuid job_id PK
 uuid user_id FK
 string status
 string input_hash
 datetime created_at
 datetime completed_at
 }
 MEDIA_ASSETS {
 uuid asset_id PK
 uuid job_id FK
 string asset_type
 string storage_reference
 string sha256
 bigint duration_ms
 }
 JOB_EVENTS {
 uuid event_id PK
 uuid job_id FK
 string previous_state
 string new_state
 datetime event_time
 }
 ANALYSIS_RUNS {
 uuid run_id PK
 uuid job_id FK
 uuid model_version_id FK
 string branch
 string status
 json result_reference
 }
 MODEL_VERSIONS {
 uuid model_version_id PK
 uuid experiment_id FK
 string model_name
 string version
 string approval_status
 string artifact_reference
 }
 EVIDENCE_FINDINGS {
 uuid finding_id PK
 uuid run_id FK
 bigint timestamp_ms
 int frame_index
 json region
 string evidence_type
 float score
 }
 ASSESSMENTS {
 uuid assessment_id PK
 uuid job_id FK
 string classification
 string uncertainty_status
 json supporting_evidence
 }
 REPORTS {
 uuid report_id PK
 uuid assessment_id FK
 string storage_reference
 string sha256
 datetime generated_at
 }
 DATASETS {
 uuid dataset_id PK
 string name
 string version
 string license
 string manifest_reference
 }
 EXPERIMENTS {
 uuid experiment_id PK
 uuid dataset_id FK
 string experiment_name
 json configuration
 json metrics
 }
 AUDIT_EVENTS {
 uuid audit_id PK
 uuid job_id FK
 string actor
 string action
 datetime created_at
 }
```

This is a conceptual ER diagram. Exact SQL types, indexes, foreign-key policies, partitioning and database choice remain open.

## 8. Infrastructure and deployment architecture

```mermaid
flowchart TB
 USER[User Browser] --> FRONT[Frontend Application]
 subgraph APPHOST[Application Environment]
 API[FastAPI Application]
 AUTH[Authentication and Authorization]
 ORCH[Job Orchestrator]
 end
 subgraph WORKERS[Background Processing Environment]
 QUEUE[Task Queue]
 MEDIA[Media Processing Worker]
 S[Spatial Inference Worker]
 T[Temporal Inference Worker]
 AV[Audio-Visual Inference Worker]
 F[Fusion and Report Worker]
 end
 subgraph DATA[Data Environment]
 DB[(Relational Database)]
 OBJ[(Media Object Storage)]
 ART[(Model Artifact Storage)]
 EXP[(Experiment Storage)]
 end
 subgraph ML[Model Environment]
 REG[Model Registry]
 SP[Spatial Model]
 TP[Temporal Model]
 AP[Audio-Visual Model]
 FP[Fusion Configuration]
 end
 subgraph OPS[Operations and Security]
 LOG[Centralized Logging]
 MON[Performance Monitoring]
 AUDIT[Audit Trail]
 BACKUP[Backup and Recovery]
 end
 FRONT <--> API --> AUTH --> ORCH --> QUEUE --> MEDIA
 MEDIA --> S & T & AV
 S --> F
 T --> F
 AV --> F
 API <--> DB
 ORCH <--> DB
 MEDIA <--> OBJ
 F --> DB & OBJ
 REG --> SP & TP & AP & FP
 SP --> S
 TP --> T
 AP --> AV
 FP --> F
 API --> LOG
 ORCH --> LOG
 MEDIA --> LOG
 S --> MON
 T --> MON
 AV --> MON
 AUTH --> AUDIT
 ORCH --> AUDIT
 DB --> BACKUP
 OBJ --> BACKUP
 ART --> BACKUP
 EXP --> BACKUP
```

| Environment | Components |
|---|---|
| Development laptop | Source code, tests, API, small experiments |
| GPU training environment | Model training and evaluation |
| Application server | Frontend/backend and orchestration |
| Worker environment | Media processing and inference |
| Database environment | Structured application records |
| Object storage | Videos and evidence artifacts |
| Model storage | Checkpoints and approved models |

Local CPU development is a reasonable starting point; large CUDA-based training requires a suitable NVIDIA GPU environment. Actual resource requirements depend on the chosen models.

## 9. Testing, evaluation and quality architecture

```mermaid
flowchart TD
 CODE[Code Changes] --> UNIT[Unit Tests] --> CONTRACT[Contract Tests] --> INTEGRATION[Integration Tests] --> E2E[End-to-End Tests] --> MEDIA[Media Input Tests] --> FAILURE[Failure and Recovery Tests] --> ML[ML Evaluation]
 ML --> CLASS[Classification Metrics] & FRAME[Frame and Region Localization] & SEG[Temporal Localization] & AV[Audio-Visual Evaluation]
 CLASS --> ROBUST[Robustness Evaluation]
 FRAME --> ROBUST
 SEG --> ROBUST
 AV --> ROBUST
 ROBUST --> CROSS[Cross-Dataset Evaluation] --> CAL[Calibration Evaluation] --> PERF[Performance and Resource Evaluation] --> SECURITY[Security and Privacy Testing] --> RELEASE{Release criteria met?}
 RELEASE -->|No| FIX[Fix and Re-evaluate] --> CODE
 RELEASE -->|Yes| APPROVE[Approve Version] --> DEPLOY[Deploy Model / Application] --> MONITOR[Monitor Production Behavior]
```

| Capability | Measurements |
|---|---|
| Video classification | ROC-AUC, precision, recall, F1 |
| Frame detection | Frame-level precision, recall, F1 |
| Region localization | IoU, AP |
| Temporal localization | Temporal IoU, segment AP |
| Audio-visual | Synchronization accuracy/error |
| Calibration | Brier score, expected calibration error |
| Runtime | Latency, throughput, memory |
| Robustness | Cross-dataset performance and degradation |

## 10. Complete project development map

```mermaid
flowchart TD
 P0[Phase 0: Research and Architecture] --> P1[Phase 1: Repository and Backend Foundation] --> P2[Phase 2: Media Ingestion and Processing] --> P3[Phase 3: Spatial Detection Baseline] --> P4[Phase 4: Temporal Detection] --> P5[Phase 5: Audio-Visual Detection] --> P6[Phase 6: Evidence Fusion and Uncertainty] --> P7[Phase 7: Frontend and Forensic Reporting] --> P8[Phase 8: Robustness, Security and Validation] --> P9[Phase 9: Release and Demonstration]
 P0 -.-> D[Literature Review, Dataset Audit, Research Gap]
 P1 -.-> R[GitHub, API, Database, Testing]
 P2 -.-> M[FFmpeg, OpenCV, Face Tracking, Audio]
 P3 -.-> S[Spatial Baseline, Training, Evaluation]
 P4 -.-> T[Video Sequence, Temporal Model]
 P5 -.-> A[Audio-Visual Synchronization]
 P6 -.-> F[Evidence Contracts, Fusion, Calibration]
 P7 -.-> UI[Video Viewer, Evidence Timeline, Report]
 P8 -.-> V[Cross-Dataset, Robustness, Security]
 P9 -.-> RELEASE[Validated Demo, Documentation, Benchmark Results]
```

## 11. Architecture decisions and open questions

| Component | Status |
|---|---|
| NEXTRON project identity | Confirmed baseline |
| Video-first scope | Confirmed baseline |
| 10-layer architecture | Architecture baseline |
| 33 logical components including UI | Architecture baseline |
| Spatial + temporal + AV branches | Confirmed baseline |
| Evidence fusion and uncertainty | Confirmed baseline |
| Modular monolith | Recommended |
| Python + PyTorch | Recommended |
| FFmpeg + OpenCV | Recommended |
| FastAPI | Recommended |
| Dataset selection | Research pending |
| Specific model architectures | Research pending |
| Fusion algorithm | Research pending |
| Database/provider | Not selected |
| GPU provider | Not selected |
| Frontend framework | Not selected |
| Deployment infrastructure | Not selected |

## 12. Using and maintaining these diagrams

The Mermaid blocks are editable source code. Render them with [Mermaid Live Editor](https://mermaid.live/), maintain the Markdown in [GitHub](https://github.com/), or edit it in [Visual Studio Code](https://code.visualstudio.com/).

Suggested documentation layout if the master document is later split:

```text
NEXTRON/
└── docs/
    └── architecture/
        ├── 00_MASTER_ARCHITECTURE.md
        ├── 01_SYSTEM_OVERVIEW.md
        ├── 02_VIDEO_VERIFICATION_FLOW.md
        ├── 03_ML_TRAINING_ARCHITECTURE.md
        ├── 04_REPOSITORY_ARCHITECTURE.md
        ├── 05_MODULE_DEPENDENCIES.md
        ├── 06_EVIDENCE_FUSION.md
        ├── 07_DATABASE_ARCHITECTURE.md
        ├── 08_DEPLOYMENT_ARCHITECTURE.md
        ├── 09_TESTING_ARCHITECTURE.md
        └── 10_DEVELOPMENT_ROADMAP.md
```

## Next engineering milestone

Define the exact interface, inputs, outputs, dependencies, failure conditions and acceptance tests for each component before building the implementation skeleton. This is an architecture proposal, not evidence that the modules are implemented or validated. The goal is a system whose conclusions withstand technical scrutiny.
