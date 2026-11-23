# Phase B Delivery — Backend + Real SSE

**Status:** complete  
**Branch:** `design/grok-premium-cockpit`  
**Repo:** `/agent/nova-export`  
**Date:** 2026-11-23

## What shipped

### FastAPI (`apps/api`)
- Config via env (`.env.example`), CORS, SQLite + SQLAlchemy, Alembic migration `001_initial_schema`
- Error model `{code, message_fa}`
- Run model + lifecycle: create → orchestrator stages → partial/completed report
- Event store (ordered `seq`) + in-process SSE broadcaster
- `GET /api/runs/{id}/events` with `last_event_id` / `Last-Event-ID` resume and explicit `heartbeat` events (not progress)
- REST: runs, markets, select-country/buyers, feasibility, report
- Admin: login/logout Bearer sessions, providers CRUD (encrypted keys), model, usage, test-connection
- Fernet encryption for provider keys at rest; keys never returned to client / never logged
- Stub research providers only in Phase B (honest `INSUFFICIENT_EVIDENCE` / `PROVIDER_UNAVAILABLE` / `NO_BUYERS`)
- Docker Compose + API healthcheck; optional Caddy stub (`deploy/Caddyfile`, compose profile `proxy`)

### Frontend wire-up (`apps/web`)
- `live-adapter.ts` + `getApiClient()` switches on `NEXT_PUBLIC_DATA_SOURCE=live`
- Mock mode preserved; experimental/fixture UI only when mock
- `useRunEvents` SSE client with reconnect + resume
- Admin login calls real `/api/admin/login` in live mode

## How to run locally

```bash
# API
cd /agent/nova-export/apps/api
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Web (live)
cd /agent/nova-export/apps/web
cp ../../.env.example .env.local   # or export vars
# NEXT_PUBLIC_DATA_SOURCE=live
# NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
npm install && npm run dev

# Or compose
cd /agent/nova-export
docker compose up --build
```

Default admin: `admin` / `nova-dev-change-me` (change via env).

## Test evidence

```text
cd apps/api && python -m pytest tests/ -v
# 14 passed — health, admin auth, key encryption (no echo),
# run lifecycle, event ordering, store resume cursor,
# SSE HTTP heartbeat + header resume, SSE unit ordering/heartbeat≠progress,
# feasibility deterministic, buyers honest empty

cd apps/web && npm run lint && npm run typecheck
# both green
```

## Gaps / out of scope (→ Phase C)
- No live paid provider calls (by design)
- No free/live research path yet — stubs return insufficient/unavailable
- VPS production deploy not required for Phase B
- Graphify MCP unavailable

## Stop note
Original Phase B gate said stop before Phase C; employer later override continues Phase C/D in same workstream.
