# NEXTRON frontend

The public site and the investigation workspace, in one Next.js app (App Router, TypeScript).
It runs on demo data by default and switches to the NEXTRON backend with one environment variable.

```powershell
cd frontend
npm install
npm run dev        # http://localhost:8080
```

| Script | Does |
|---|---|
| `npm run dev` | Development server on port 8080 |
| `npm run build` | Production build |
| `npm start` | Serve the production build on port 8080 |
| `npm run typecheck` | TypeScript check only |

**Backend:** set `NEXT_PUBLIC_NEXTRON_API=http://localhost:8000/api/v1` in `.env.local`. Every call then goes to the
backend through `src/api/client.ts`; without it, `src/api/mock.ts` serves the demo data in the browser.
The routes and payloads the backend must provide are in [`../docs/BACKEND_API.md`](../docs/BACKEND_API.md);
what the ML pipeline must output is in [`../docs/ML_OUTPUT_SPEC.md`](../docs/ML_OUTPUT_SPEC.md).

## Folders

```
frontend/
├── public/images/            evidence stills, the landing exhibit, social preview
├── src/
│   ├── app/                  routes only (Next.js App Router): one folder per address
│   │   ├── page.tsx          /  the landing page
│   │   ├── not-found.tsx     every unbuilt or unknown address (HTTP 404)
│   │   └── (workspace)/      every workspace address, sharing one shell (layout.tsx)
│   ├── layouts/              MainLayout (shell + navigation), Sidebar, Topbar, Breadcrumbs, CommandPalette
│   ├── modules/              one folder per product area; screens.tsx connects them to the shell
│   │   ├── landing/  dashboard/  investigations/  evidence/  evidence-graph/
│   │   └── reports/  notifications/  system/  settings/
│   ├── components/ui/        shared primitives (Dot, Thumb, FindingMark, PageHead, Skeleton…)
│   ├── components/feedback/  the 404 page
│   ├── api/                  contract.ts (types), endpoints.ts (REST table), client.ts (HTTP), mock.ts + fixtures.ts (demo)
│   ├── stores/               workspace.store.tsx: data for the session, optimistic actions, analysis polling
│   ├── config/               routes.ts (every address, as functions), navigation.ts (the sidebar)
│   ├── utils/                labels.ts: every label and colour for the contract's enums
│   ├── styles/               globals.css, workspace.module.css (the workspace design system)
│   └── proxy.ts              answers 404 for unknown case/report IDs and analysis types
└── tests/                    unit, components, routes, integration, e2e
```

Not created yet, because nothing needs them: `realtime/` (arrives with the backend's WebSocket/SSE events),
`hooks/` beyond the store, and `schemas/` (the contract in `src/api/contract.ts` is the single schema today).

## Addresses

Built (everything else in the sitemap answers **404** until its page exists):

| Address | Page |
|---|---|
| `/` | Landing |
| `/dashboard` | Dashboard: the most urgent case, decisions waiting, all investigations |
| `/investigations` · `/active` · `/completed` · `/archived` | Investigation list and its filters |
| `/investigations/new` | New investigation: scan and seal evidence |
| `/investigations/:caseId` | Case overview |
| `…/evidence` · `…/evidence/add` | The case's evidence; add evidence |
| `…/analysis` · `…/analysis/image\|video\|audio\|provenance` | Findings, all or by media type |
| `…/timeline` · `…/graph` · `…/review` · `…/report` · `…/events` | Case timeline, graph, review queue, report studio, event log |
| `/evidence` | All evidence |
| `/evidence/:id` · `/preview` · `/analysis` · `/timeline` · `/metadata` | The evidence workbench, one address per tool (`?finding=F-021` selects a finding) |
| `/evidence/:id/integrity` | Hash, preservation and custody trail |
| `/graph` | Evidence graph across cases |
| `/reports` · `/reports/:id` · `/reports/:id/preview` | Reports, the studio, a read-only preview |
| `/notifications` | Decisions waiting and activity |
| `/system` · `/system/health` · `/system/logs` | Governance, health, audit log |
| `/settings` | Preferences for this browser |

Not built yet (404): sources and connectors, lineage, intelligence, graph node/edge pages, report history,
evidence versions and history, help, the remaining system and settings pages, and the case sources, lineage and settings tabs.
To build one, add its folder under `src/app/(workspace)/`, its helper in `src/config/routes.ts`, and, if it belongs
in the sidebar, an entry in `src/config/navigation.ts`.

`/workspace` (the old single-page address) redirects to `/dashboard`.
