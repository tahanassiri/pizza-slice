# NOVA Export Intelligence — Final Delivery

**Product:** private Persian/RTL export-market demo (Pizza Slice)  
**Branch:** `design/grok-premium-cockpit` (`8cbf29b`)  
**Repo path:** `/agent/nova-export`  
**Date:** 2026-11-23  
**Git remote:** none configured in this environment — commit is local only (no push)

## Phases

| Phase | Status | Notes |
|-------|--------|-------|
| A Frontend mock MVP + Command Bridge UI | ✅ | Mock labeled «داده آزمایشی» |
| B Backend + real SSE + admin vault | ✅ | [phase-b-delivery.md](./phase-b-delivery.md) |
| C Live-capable free path | ✅ | [phase-c-delivery.md](./phase-c-delivery.md) |
| D Acceptance | ✅ | 25 API pytest + live WB smoke |

## How to run (local)

```bash
# API
cd /agent/nova-export/apps/api
pip install -r requirements.txt
# optional: cp ../../.env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Web (live)
cd /agent/nova-export/apps/web
export NEXT_PUBLIC_DATA_SOURCE=live
export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
npm install && npm run dev
```

Or:

```bash
cd /agent/nova-export
docker compose up --build
# optional proxy: docker compose --profile proxy up
```

**Admin default:** `admin` / `nova-dev-change-me` (override via env).  
**Mock-only UI:** `NEXT_PUBLIC_DATA_SOURCE=mock` (never mixed with live runs).

## Test evidence

```text
cd apps/api && python -m pytest tests/ -v
# 25 passed — health, admin auth/key encryption, SSE order/resume/heartbeat≠progress,
# Phase C registry+WB markets, Phase D 10-run isolation, invalid product,
# missing-key buyers empty, RATE_LIMITED surface, feasibility math, report fields

Live smoke PROVIDER_MODE=auto → 3 markets (CN, DE, IN), is_mock=false

cd apps/web && npm run lint && npm run typecheck
# green
```

## Acceptance checklist (blueprint §8)

- [x] Independent run per product text
- [x] Stages update via SSE without claiming fake progress (heartbeat ≠ progress)
- [x] ≤3 markets with evidence/sources OR honest insufficient
- [x] Country select → buyers empty/honest when unverified (no fake list)
- [x] Editable costs + deterministic scenarios
- [x] Report with findings, risks, assumptions, sources (print HTML)
- [x] Admin can set providers/model/keys server-side only
- [x] Keys never in frontend / response bodies / logs
- [ ] Private VPS HTTPS demo — **not auto-deployed** (no production secrets/VPS automation in this environment)

## VPS steps (manual — do not wait)

1. Clone private repo on VPS; copy `.env.example` → `.env` with strong `ADMIN_PASSWORD`, `SESSION_SECRET`, `SECRETS_FERNET_KEY`
2. `docker compose up -d --build` (or Caddy profile for single entry)
3. Put TLS in front (Caddy/nginx); keep compose ports firewalled to proxy only
4. Confirm `NEXT_PUBLIC_DATA_SOURCE=live` and API base URL reachable from the browser
5. Login admin; optionally add free/paid keys — paid keys optional; free WB path works without them
6. Do **not** make the repo public; do **not** enable paid plans from this agent

## Gaps / next (optional)
- Product-HS-specific trade (Comtrade) when a free/key path is approved
- Verified buyer enrichment only with explicit evidence rules
- Graphify MCP was unavailable during this work
- Mobile visual QA was Phase A; re-spot-check live mode on a phone after compose up

## Autonomy / safety followed
- No paid API billing; no public push; secrets server-side only
- Stub/unavailable when keys missing
- Mock labels only for mock data source
