# NOVA Export Intelligence

Private Persian/RTL demo: product → markets → buyers → feasibility → printable report.

## Quick start

```bash
# API
cd apps/api && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Web (live backend)
cd apps/web
export NEXT_PUBLIC_DATA_SOURCE=live
export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
npm install && npm run dev
```

Compose: `docker compose up --build` from repo root.

Defaults: admin `admin` / `nova-dev-change-me`. See `.env.example`.

- `NEXT_PUBLIC_DATA_SOURCE=mock` — Phase A fixtures only  
- `PROVIDER_MODE=auto` — free World Bank/Wiki (+ keyed providers if configured)  
- `PROVIDER_MODE=stub` — no external calls  

## Tests

```bash
cd apps/api && python -m pytest tests/ -v
cd apps/web && npm run lint && npm run typecheck
```

## Docs

- `docs/ARCHITECTURE.md`, `docs/API_CONTRACTS.md`, `docs/PROVIDERS.md`, `docs/DEMO_ACCEPTANCE.md`
