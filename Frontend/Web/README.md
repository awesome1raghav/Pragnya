# NEXTRON frontend

The investigation workspace and the public landing page, in one Next.js app (App Router, TypeScript).
Every workspace page reads the real NEXTRON API. There is no mock mode: if the API is down, the pages say so.

```powershell
cd frontend\Web          # use the folder's on-disk casing; see "Known issue" below
npm ci --workspaces=false
npm run dev              # http://localhost:8080 (the API must run on http://localhost:8000)
```

| Script | Does |
|---|---|
| `npm run dev` | Development server on port 8080 |
| `npm run build` | Production build |
| `npm start` | Serve the production build on port 8080 |
| `npm run typecheck` | TypeScript check only |

**API address:** `http://localhost:8000/api/v1` by default. To change it, copy `.env.example` to `.env.local`
and set `NEXT_PUBLIC_NEXTRON_API`. The API's shapes are mirrored in `src/api/types.ts` from its OpenAPI
(`http://localhost:8000/docs`).

**End-to-end tests:** `Tests/End-To-End` (Playwright) runs against the running frontend and API:
`cd Tests\End-To-End; npm install --workspaces=false; npx playwright install chromium; npx playwright test`.

## Folders

```
Frontend/Web/
├── public/images/          landing exhibit and social preview
└── src/
    ├── app/                routes only: one folder per address
    │   ├── about/          /about, the landing page (/ redirects to /dashboard)
    │   ├── not-found.tsx   unknown addresses (HTTP 404)
    │   └── (workspace)/    every application address, sharing one shell
    ├── api/                index.ts (every call, by API domain), http.ts (transport + ApiError),
    │                       types.ts (API shapes), query.ts (cache, invalidation), hooks.ts (typed reads)
    ├── state/              CaseContext.tsx: the active investigation, taken from the address
    ├── layouts/            MainLayout (shell), Sidebar, Topbar, Breadcrumbs, SearchPalette, JobMonitor, SystemStatus
    ├── modules/            dashboard, investigations, evidence, intelligence, pending (not-yet-built areas), system, settings, landing
    ├── components/         ui/ (states, PageHead, Hash, Pager…), CaseScope.tsx, feedback/ (404)
    ├── config/             routes.ts (every address), navigation.ts (the eleven destinations)
    ├── utils/labels.ts     labels and colours for the API's codes, formatting helpers
    ├── styles/             workspace.module.css (design system), platform.module.css (states, forms, rows, module map)
    └── demo/               the earlier mock-data prototype, not routed; kept for its designs (see demo/README.md)
```

## Addresses (Flowchart B)

| Address | Page | Data today |
|---|---|---|
| `/` | Redirects to `/dashboard` | — |
| `/dashboard` | Counts, recently active investigations, recent activity, system health, jobs | Live; jobs and findings shown as not built |
| `/investigations` · `/active` · `/completed` · `/archived` | Server-side search, filters, sorting, paging | Live |
| `/investigations/new` | Create an investigation (objectives, category, priority…) | Live |
| `/investigations/:caseId` (+ evidence, evidence/add, timeline, events) | The investigation workspace | Live |
| `/investigations/:caseId` analysis, graph, review, report | Workspace tabs | Not built yet (Steps 3–7) |
| `/evidence` (`?case=` to scope) | Evidence inventory | Live |
| `/evidence/:id` (+ preview, metadata, integrity, timeline) | Original, metadata, integrity check, custody | Live |
| `/evidence/:id/analysis` | Forensic analysis | Not built yet |
| `/intelligence` | The 18 modules, their connectivity and status | Live (from `/system/modules`) |
| `/sources` · `/lineage` · `/graph` · `/reports` · `/notifications` | Their purpose and the module that will provide them | Not built yet |
| `/system` · `/system/health` · `/system/logs` | Measured health, database, storage, modules | Live; workers and logs not built |
| `/settings` | Browser preferences, read-only installation facts | Live |
| `/about` | Landing page | Static |

## Known issue: folder casing

Git tracks this folder as `Frontend/`, but on this machine it exists on disk as `frontend/`. Windows tolerates
the difference for most tools, but the Turbopack dev server fails to resolve its Google Fonts module when started
through the `Frontend/Web` spelling (for example via the root `package.json` scripts). Start it from `frontend\Web`
until the folder is renamed on disk to match Git.
