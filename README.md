# NEXTRON

**Intelligent Deepfake & Digital Media Verification System**

NEXTRON is an enterprise-grade digital media verification platform designed for forensic investigators, security analysts, and intelligence teams reviewing suspected synthetic and manipulated video and audio-visual media.

---

## 1. Project Architecture & Organization

The repository follows a clean, standardized, modular structure separating user-facing applications, design specifications, and system documentation:

```text
NEXTRON/
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

### Running the Frontend Application

The user-facing application is built on Next.js 16 (App Router) with TypeScript and Tailwind/CSS Modules. It operates seamlessly with an integrated in-memory mock engine or connects to a live NEXTRON backend.

```bash
# Navigate to the frontend directory
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

The standalone prototype demonstrates early visual design explorations and can be viewed directly:
- Open `Design/Prototype/index.html` in any modern web browser.

---

## 3. Technology Stack & Key Specifications

- **Frontend Core:** Next.js 16, React 19, TypeScript, CSS Modules
- **Forensic Pipeline:** Spatial Detection, Temporal Consistency, Audio-Visual Alignment, and Multi-Branch Evidence Fusion
- **API Standard:** OpenAPI / RESTful JSON with strict TypeScript contract definitions (`Frontend/src/api/contract.ts`)
- **Documentation Standards:** Comprehensive Markdown with Mermaid diagrams and mathematical rigor

---

## 4. Documentation Index

For in-depth specifications and engineering guidelines, consult the `Documentation/` directory:
- [NEXTRON Master Architecture](Documentation/NEXTRON%20Master%20Architecture.md)
- [NEXTRON Frontend Architecture](Documentation/NEXTRON%20Frontend%20Architecture.md)
- [Backend API Specification](Documentation/Backend%20API%20Specification.md)
- [ML Output Specification](Documentation/ML%20Output%20Specification.md)
- [Workspace Visual UX Audit](Documentation/Workspace%20Visual%20UX%20Audit.md)
