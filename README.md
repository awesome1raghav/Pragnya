# NEXTRON

**Intelligent Deepfake & Digital Media Verification System**

NEXTRON is an enterprise-grade digital media verification platform designed for forensic investigators, security analysts, and intelligence teams reviewing suspected synthetic and manipulated video and audio-visual media.

---

## 1. Project Architecture & Organization

The repository follows a clean, standardized, modular structure separating user-facing applications, backend microservices, design specifications, and system documentation:

```text
NEXTRON/
│
├── Backend/                        # FastAPI asynchronous backend application & orchestration engine
│   ├── App/                        # Application source code
│   │   ├── Api/V1/                 # Versioned REST API routes & controllers
│   │   ├── Audit/                  # Forensic event recording & chain of custody logging
│   │   ├── Core/                   # Security, middleware, permissions, exceptions, constants
│   │   ├── Modules/                # The 18 official NEXTRON domain engines (NexCm to NexRpt)
│   │   ├── Orchestration/          # T-MIR pipeline & multi-branch forensic execution engine
│   │   ├── Realtime/               # WebSocket connections & realtime forensic event publisher
│   │   ├── Schemas/                # Pydantic data validation schemas & DTOs
│   │   ├── Services/               # High-level domain service adapters
│   │   ├── Storage/                # File storage management & integrity checks
│   │   ├── Utils/                  # Cryptographic hashing, binary, and media utilities
│   │   └── Workers/                # Asynchronous job dispatchers, executors, and tasks
│   ├── Database/                   # Multi-model database architecture
│   │   ├── PostgreSQL/             # Relational models, migrations, repositories & indexes
│   │   ├── Neo4j/                  # Graph repository, node/relationship managers & Cypher queries
│   │   ├── Qdrant/                 # Vector collections, embeddings repository & ANN search
│   │   └── Redis/                  # Distributed cache, lock coordination & connection pools
│   ├── Documentation/              # Backend, database, API, and T-MIR architectural documentation
│   ├── Scripts/                    # Database migrations, seeding, and administrative scripts
│   ├── Storage/                    # Storage roots (Originals, Derived, Thumbnails, Frames, Audio, etc.)
│   ├── Tests/                      # Unit, integration, end-to-end, and security test suites
│   ├── alembic.ini                 # Alembic database migration configuration
│   ├── pyproject.toml              # Modern Python packaging configuration
│   ├── requirements.txt            # Python dependencies manifest
│   └── README.md
│
├── Design/                         # UI/UX design specifications, prototypes, and visual assets
│   ├── Implementation Plan.md      # Design implementation details and visual direction
│   ├── landing-desktop.png         # Desktop interface design mockups
│   ├── landing-mobile.png          # Mobile responsive layout references
│   ├── landing-reference.png       # Forensic console visual references
│   └── Prototype/                  # Standalone lightweight HTML5/CSS3 forensic landing prototype
│       ├── index.html
│       ├── styles.css
│       └── app.js
│
├── Documentation/                  # System specifications, architecture baselines, and research
│   ├── NEXTRON Master Architecture.md      # Comprehensive 10-layer system architecture baseline
│   ├── NEXTRON Frontend Architecture.md    # Frontend application architecture and component design
│   ├── Backend API Specification.md        # REST API contracts and endpoint documentation
│   ├── ML Output Specification.md          # Multi-branch ML inference output schemas
│   └── Workspace Visual UX Audit.md        # Comprehensive visual, accessibility, and UX audit
│
├── Frontend/                       # Next.js 16 (App Router) + TypeScript production application
│   ├── public/                     # Public static assets and forensic evidence datasets
│   ├── src/                        # Modular application source code
│   │   ├── api/                    # API client, contracts, endpoints, and mock engine
│   │   ├── app/                    # Next.js App Router route hierarchy
│   │   ├── components/             # Reusable UI primitives and feedback components
│   │   ├── config/                 # Route declarations and navigation configurations
│   │   ├── layouts/                # MainLayout, Sidebar, Topbar, Breadcrumbs, CommandPalette
│   │   ├── modules/                # Domain feature modules (evidence, investigations, etc.)
│   │   ├── stores/                 # State management and workspace data stores
│   │   ├── styles/                 # Global styles and modular CSS design tokens
│   │   └── utils/                  # Utility helpers and forensic label formatters
│   ├── package.json
│   ├── tsconfig.json
│   └── README.md
│
├── .gitignore
└── README.md
```

---

## 2. Quick Start

### Running the Backend Application

```bash
# Navigate to Backend
cd Backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start FastAPI development server
uvicorn App.Main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation will be available at:
- Swagger UI: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- ReDoc: [http://localhost:8000/api/v1/redoc](http://localhost:8000/api/v1/redoc)

### Running the Frontend Application

```bash
# Navigate to Frontend
cd Frontend

# Install dependencies
npm ci

# Start development server on port 8080
npm run dev

# Or build and start for production
npm run build
npm start
```

Open [http://localhost:8080](http://localhost:8080) in your browser.

### Inspecting the Design Prototype

The standalone prototype demonstrates early visual design explorations:
- Open `Design/Prototype/index.html` in any modern web browser.

---

## 3. Technology Stack & Key Specifications

- **Backend:** FastAPI, Python 3.11+, SQLAlchemy 2.0, Alembic, Celery, Redis, Pydantic v2
- **Frontend Core:** Next.js 16, React 19, TypeScript, CSS Modules
- **Forensic Pipeline:** Spatial Detection, Temporal Consistency, Audio-Visual Alignment, and Multi-Branch Evidence Fusion (T-MIR Orchestration)
- **API Standard:** OpenAPI / RESTful JSON with strict TypeScript contract definitions (`Frontend/src/api/contract.ts`)
- **Documentation Standards:** Comprehensive Markdown with Mermaid diagrams and mathematical rigor
