# GROK → Cursor Handoff (Frontend complete → Backend gate)

**Branch:** `design/grok-premium-cockpit`  
**Do not start backend without explicit user approval.**

## Product
NOVA Export Intelligence — private Persian/RTL demo for export market discovery, buyers, feasibility, report. Mock data always labeled «داده آزمایشی / پیش‌نمایش آزمایشی».

## Structure
```
nova-export/
  apps/web/          # Next.js App Router + TS + Tailwind
    app/             # routes: /, /analysis/[id]/*, /admin*
    components/      # shared UI (markets, buyers, feasibility, report, admin)
    features/analysis/cockpit/  # live analysis Command Bridge
    lib/api/         # typed client + mock-adapter (live swap later)
    lib/i18n/fa.ts
    types/           # Run, RunEvent, Market, Buyer, Feasibility, Report, …
    fixtures/        # happy, sparse, unavailable, quota, partial, incomplete_financial
  apps/api/          # placeholder only
  docs/              # architecture, contracts, this handoff
```

## Design language
- Midnight navy `#0B1426`, teal `#0CB6AA`, gold `#E6B765`
- Analysis: dark cockpit (hero, phase rail, evidence feed, progressive results, signal viz)
- Study panes (markets/buyers/feasibility/report): light paper inside dark chrome — not identical card farms
- Home / admin: dark Command Bridge surfaces
- See `docs/GROK_UI_DESIGN_SYSTEM.md`

## Contracts / adapter (mock → live)
- UI calls only `getApiClient()` (`lib/api/client.ts`)
- Phase A implementation: `mock-adapter.ts` + sessionStorage runs
- Types in `types/index.ts` align with blueprint REST/SSE:
  - `POST /api/runs`, `GET /api/runs/{id}`, `GET /api/runs/{id}/events` (SSE future)
  - markets, buyers, feasibility, report, admin providers
- **Never mix mock and live in one response.** Keys never in browser storage/JSX/logs.

## How to run
```bash
cd apps/web && npm install && npm run dev
npm run lint && npm run typecheck && npm run build
```

## Tests / QA done
- lint, typecheck, build green
- Visual QA screenshots for home, cockpit, markets, buyers, feasibility, report, admin, mobile

## Limits
- No real Tavily/Exa/Gemini/Comtrade calls
- Admin auth is cosmetic (`sessionStorage.nova_admin_demo`)
- Graphify MCP was not available during this work
- No deploy / no paid services

## Backend next (Phase B) — only after approval
1. FastAPI + SQLite + run lifecycle + real SSE events
2. Secure admin key vault (server-side only)
3. Wire live adapter behind `getApiClient()` without rewriting pages
4. Docker Compose + healthcheck
5. Keep mock fixtures for local UI without keys
