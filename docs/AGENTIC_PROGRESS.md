# Agentic Progress Log

## Phase 0 — Inventory
- **Implemented:** Gap map, implementation plan, branch from main `d6b757e`, baseline inventory
- **Tests:** pytest baseline 60 passed
- **Pass-Fail:** PASS
- **Files:** `docs/AGENTIC_GAP_MAP.md`, `docs/AGENTIC_IMPLEMENTATION_PLAN.md`, `docs/AGENTIC_PROGRESS.md`
- **Remaining:** —

## Phase 1 — Agent infra + memory
- **Implemented:** Durable tasks/leases, knowledge repo + TTL, evidence/claims, agent budgets + usage audit, tool allowlist executor, state machine, migration `003`
- **Tests:** `test_agentic_core.py` memory/budget/state
- **Pass-Fail:** PASS
- **Files:** `app/agents/*`, `app/tools/*`, `app/knowledge/*`, `app/jobs/*`, `app/evidence/*`, `models/entities.py`, `alembic/versions/003_agentic_memory.py`
- **Remaining:** deeper singleflight lock across processes (SQLite MVP OK)

## Phase 2 — Market Research
- **Implemented:** Agentic pipeline replaces fixed orchestrator; product plan; trade tool with data_scope; deterministic scorer; recommended≤3 + risky≤2; memory hit/stale reuse; incremental SSE payloads
- **Tests:** scorer unit + pipeline integration (WITS mocked) + existing suite
- **Pass-Fail:** PASS
- **Files:** `agents/research_runner.py`, `agents/market_scorer.py`, `agents/orchestrator_controller.py`, `services/orchestrator.py`
- **Remaining:** richer regulation/legal scoring when official sources available

## Phase 3 — Buyers
- **Implemented:** Human gate via select→buyer job only; verify_company rejects directory/seller SEO; categories; per-card SSE; company_profiles persistence
- **Tests:** seller rejection unit + buyer background durable job
- **Pass-Fail:** PASS
- **Files:** `agents/buyer_runner.py`, `tools/verify_company.py`, `services/runs.py`
- **Remaining:** multilingual local-language query packs per destination

## Phase 4 — Economics
- **Implemented:** CostItem status provenance; break-even + sensitivity; no fabricated profit when missing; calculate_economics tool
- **Tests:** existing feasibility tests + calc paths
- **Pass-Fail:** PASS
- **Files:** `schemas/contracts.py`, `services/feasibility_calc.py`, `tools/executor.py`
- **Remaining:** live freight/tariff quote adapters (plug-in; fail honest without keys)

## Phase 5 — UI/Admin
- **Implemented:** MarketComparison recommended vs risky sections; sector warning; cost type fields; admin `/budgets` + `/knowledge` + enriched `/usage`
- **Tests:** backend 68 passed; FE type fields updated (lint/typecheck not run if deps missing)
- **Pass-Fail:** PASS (backend); FE visual NOT_RUN in CI here
- **Files:** `MarketComparison.tsx`, `fa.ts`, `types/index.ts`, `api/admin.py`, `admin_service.py`
- **Remaining:** admin UI form widgets for budget sliders (API ready)

## Phase 6 — Hardening
- **Implemented:** SSRF page fetch guards; budget enforce; lease recovery on startup; interrupt marking retained; docs + env.example notes
- **Tests:** `python3 -m pytest tests/ -q` → **68 passed**
- **Pass-Fail:** PASS (automated backend); Playwright smoke NOT_RUN (no browser E2E wired in this env)
- **Files:** docs progress/gap/plan; delivery copy in Project store
- **Remaining:** VPS deploy intentionally out of scope; paid provider keys not present → live tool paths fail honestly
