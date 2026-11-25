# NEXTRON

**Intelligent Deepfake & Digital Media Verification System**

NEXTRON is an enterprise-grade, research-grounded digital media verification platform designed for forensic investigators, security analysts, and intelligence teams reviewing suspected synthetic, manipulated, and cross-platform video and audio-visual media.

---

## 1. Complete End-to-End Project Architecture

The workspace is organized into a modular, production-ready structure where every area of the system has explicit ownership:

```text
NEXTRON/
│
├── Backend/                        # Core intelligence system: APIs, 18 forensic engines, T-MIR, workers
│   ├── App/                        # FastAPI application, Core, Modules (NexCm..NexRpt), Orchestration
│   ├── Database/                   # Multi-model database drivers (PostgreSQL, Neo4j, Qdrant, Redis)
│   ├── Documentation/              # Backend and module engineering specifications
│   ├── Scripts/                    # Lifecycle startup & backend initialization scripts
│   ├── Storage/                    # Partitioned storage volumes (Originals, Derived, Thumbnails, etc.)
│   ├── Tests/                      # Backend unit, integration, and security test suites
│   ├── alembic.ini                 # Database migrations configuration
│   ├── pyproject.toml              # Modern Python build metadata
│   ├── requirements.txt            # Python dependencies manifest
│   └── README.md
│
├── Frontend/                       # Multi-client user interface platform
│   ├── Web/                        # Next.js 16 (App Router) + TypeScript forensic investigator dashboard
│   ├── Android/                    # Native Android mobile client & Floating Bubble capture service
│   │   ├── App/                    # Mobile evidence review and intake application
│   │   └── FloatingBubble/         # System overlay capture service with user authorization
│   └── Desktop/                    # High-throughput workstation desktop client
│
├── Database/                       # Independent database infrastructure & setup
│   ├── PostgreSQL/                 # Authoritative schemas, migrations, procedures, and backup
│   ├── Neo4j/                      # Graph schemas, constraints, indexes, and Cypher queries
│   ├── Qdrant/                     # Vector collections, payload schemas, and vector indexing
│   ├── Redis/                      # Caching and coordination documentation
│   ├── Docker/                     # Standalone multi-model database Docker Compose environment
│   └── Database Architecture.md    # Multi-model persistence and transactional outbox specifications
│
├── Datasets/                       # Research media, benchmark ground truth, and evaluations
│   ├── Original Media/             # Pristine reference media (Images, Videos, Audio)
│   ├── Manipulated Media/          # Controlled synthetic & manipulated media
│   ├── Reencoded Media/            # Compression and re-encoding evaluation samples
│   ├── Transformed Media/          # Geometric, temporal, and adversarial transformations
│   ├── NEXTRON-MV/                 # Multimodal verification benchmark with strict split partitions
│   ├── External Datasets/          # FaceForensics++, DFDC, DeeperForensics, ASVspoof references
│   └── Dataset Licensing.md        # Provenance, SHA-256 integrity, and licensing policies
│
├── Tests/                          # Centralized multi-tier quality assurance
│   ├── Unit Tests/                 # Unit tests (Backend, Frontend, Android, Desktop)
│   ├── Integration Tests/          # Service and database integrations (PostgreSQL, Neo4j, Qdrant, T-MIR)
│   ├── System Tests/               # End-to-end investigation lifecycle verification
│   ├── End To End/                 # User-facing browser and application workflow tests
│   ├── Performance/                # Latency, throughput, and vector search benchmarks
│   ├── Security/                   # Authentication, upload sandboxing, and penetration tests
│   └── Reliability/                # Worker failure, retry handling, and disaster recovery
│
├── Documentation/                  # Technical and investigator documentation
│   ├── Project Overview/           # Vision, problem statement, objectives, and scope
│   ├── Architecture/               # System, backend, frontend, and database architecture baselines
│   ├── Modules/                    # Module catalogue and individual specifications
│   ├── T-MIR/                      # Research methodology, execution pipeline, and correlation logic
│   ├── API/                        # REST and WebSocket interface specifications
│   ├── Database/                   # ERDs, graph models, and vector embeddings schemas
│   ├── Security/                   # Threat models, data retention, and privacy policies
│   ├── Testing/                    # Testing strategy and benchmark methodologies
│   └── User Guides/                # Guides for investigators, web, Android, and desktop users
│
├── Design/                         # UI/UX design specifications, tokens, and prototypes
│   ├── Brand Identity/             # Logo, typography, color palettes, and guidelines
│   ├── User Flows/ & Wireframes/   # Interaction specifications
│   ├── UI Screens/                 # High-fidelity screen designs for all views
│   └── Prototype/                  # Standalone lightweight HTML5/CSS3 forensic landing prototype
│
├── Infrastructure/                 # Containerization, deployment, and cloud operations
│   ├── Docker/                     # Production Dockerfiles (Backend, Frontend, Worker) & compose
│   ├── Environments/               # Environment-specific manifests (Dev, Testing, Staging, Prod)
│   ├── Kubernetes/                 # Microservice deployment manifests and scaling policies
│   ├── CI-CD/                      # Build, test, security, and deployment pipelines
│   └── Monitoring/                 # Prometheus metrics, Loki logs, and Grafana dashboards
│
├── Research/                       # Scientific research foundation and experimental logs
│   ├── Literature Review/          # Formal reviews of spatial, temporal, and multimodal forensics
│   ├── T-MIR/                      # Research hypotheses, methodology, and novelty assessments
│   ├── Experiments/                # Experimental runs across image, video, and audio signals
│   └── Evaluation/                 # Metrics, baselines, and ablation study records
│
├── Scripts/                        # Automated project operations and maintenance
│   ├── Setup/                      # Dependency installation and environment bootstrap
│   ├── Development/                # Local service orchestration scripts
│   ├── Database/                   # Migration, backup, and restore runners
│   ├── Datasets/                   # Dataset validation and SHA-256 manifest generation
│   ├── Testing/                    # Centralized test execution and report generation
│   └── Maintenance/                # Evidence integrity verification and health checks
│
├── Tools/                          # Internal developer & investigator forensic utilities
│   ├── Media Inspector/            # Detailed container and stream diagnostics
│   ├── Hash Verification/          # Tamper-evident SHA-256 seal verification
│   ├── Metadata Viewer/            # Deep EXIF, XMP, and container metadata parsing
│   ├── Fingerprint Generator/      # Perceptual and neural fingerprinting utility
│   └── Benchmark Runner/           # Standardized model evaluation harness
│
├── Security/                       # Cryptographic policies, compliance, and threat models
│   ├── Threat Models/              # STRIDE and forensic attack vector analysis
│   ├── Role Based Access/          # Investigator permission boundaries
│   └── Security Documentation.md   # System security baseline
│
├── .github/                        # GitHub Actions CI/CD workflows & issue templates
├── .gitignore                      # Git ignore rules for node_modules, .venv, media binaries
├── .gitattributes                  # LF line-ending normalization
├── .editorconfig                   # Consistent multi-language editor formatting
├── LICENSE                         # Apache 2.0 open-source license
├── CONTRIBUTING.md                 # Contributor guidelines and workflow
├── CODE_OF_CONDUCT.md             # Contributor Covenant Code of Conduct
├── SECURITY.md                     # Vulnerability reporting protocol
├── CHANGELOG.md                    # Release history and milestone tracker
├── Makefile                        # Unified command launcher for development and testing
├── README.md                       # Master project overview and quick start
└── VERSION                         # Semantic version identifier (1.0.0)
```

---

## 2. Quick Start

### 1. Launch Multi-Model Database (PostgreSQL, Neo4j, Qdrant, Redis)

```bash
cd Database/Docker
docker-compose up -d
```

### 2. Launch Backend Service

```bash
cd Backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn App.Main:app --host 0.0.0.0 --port 8000 --reload
```

- API Docs: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)

### 3. Launch Frontend Web Workspace

```bash
cd Frontend/Web
npm ci
npm run dev        # Serves Next.js workspace at http://localhost:8080
```

---

## 3. Core Architectural Principles

1. **One Source of Truth:** PostgreSQL is the authoritative system of record for all cases, evidence, findings, and audit events. Neo4j and Qdrant act as rebuildable projections.
2. **Preserve Originals:** Uploaded evidence is SHA-256 sealed immediately upon intake and never overwritten. All derived media assets receive unique, immutable identifiers.
3. **Reproducibility:** Every analysis execution records model version, parameters, execution time, and input hash.
4. **Untrusted Input Isolation:** All media decoding and FFmpeg parsing occurs inside sandboxed, isolated worker containers.
5. **Human-in-the-Loop:** Forensic detection outputs are probabilistic findings with calibrated uncertainty, strictly separated from investigator judgments.
