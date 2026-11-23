# NOVA web e2e (Playwright)

## Install (once per machine)

```bash
cd apps/web
npm install
npx playwright install chromium
# Linux CI / headless hosts may also need:
npx playwright install-deps chromium
```

## Run smoke (default: local API)

Starts FastAPI on `:8000` with `PROVIDER_MODE=stub` and Next on `:3000` with `NEXT_PUBLIC_DATA_SOURCE=live`, then:

1. Loads Persian RTL home
2. Submits product form (“شروع تحلیل صادرات”)
3. Asserts navigation to `/analysis/<run_id>` and cockpit chrome

```bash
cd apps/web
npm run test:e2e
```

## Fixture-only (no API)

Uses the Next mock adapter as the documented fixture server:

```bash
E2E_DATA_SOURCE=mock npm run test:e2e
```

## Reuse already-running servers

```bash
# Terminal A — API
cd apps/api && PROVIDER_MODE=stub python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal B — Web
cd apps/web && NEXT_PUBLIC_DATA_SOURCE=live NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run dev -- --hostname 127.0.0.1 --port 3000

# Terminal C
cd apps/web && E2E_SKIP_WEBSERVER=1 npm run test:e2e
```
