# Agentic Gap Map (Phase 0)

**HEAD:** `d6b757e` (main) · **Branch:** `feat/agentic-market-research`  
**Baseline tests:** 60 passed (2026-11-23)

## Current vs target

| Module | Behavior today | Decision | Why | Migration path |
|--------|----------------|----------|-----|----------------|
| `services/orchestrator.py` | Fixed stages; LLM only `classify_hs`; markets from WITS sector sort | **REPLACE** | Not iterative research; no plan/tools/claims loop | New `agents/` controller; old pipeline removed as entry |
| `trade_data/to_markets.py` | Ranks by sector/Total import value | **REFACTOR** | Honest labels exist but UI still looks like “best product markets” | Feed as **context signal** into scorer; never sole winner |
| `trade_data/wits.py` | Free sector aggregates | **KEEP** | Correct free source if labeled | Tool `get_trade_stats` with `data_kind=sector` |
| `trade_data/research.py` | Collects URLs, no numeric invention | **REFACTOR** | Name implies deep research; only source bag | Become one tool inside research runner |
| `providers/keyed.py` `search_buyers` | Title→company, all `needs_review` | **REPLACE** path | Not verification; seller SEO risk | `tools/verify_company` + buyer agent |
| `providers/registry.py` | Resolves Tavily/Wiki/LLM/stubs | **KEEP+extend** | Working plug-in pattern | Wire tool adapters; budget enforce |
| `services/runs.py` + buyer job | Background buyer + interrupt mark | **KEEP+extend** | Durable-ish already | Gate: no buyers until select; emit SSE per verified |
| `events/*` | Persist + SSE resume | **KEEP** | Meets replay needs | New event payload types |
| `feasibility_calc.py` | Deterministic scenarios | **KEEP+extend** | Math solid | Cost provenance + research estimates |
| `models/entities.py` | Run/events/buyers/providers | **EXTEND** | No knowledge/claims/tasks/budget audit | Alembic `003_agentic_memory` |
| Admin providers UI/API | Keys encrypted, model select | **KEEP+extend** | Valuable | Enforce daily budget; usage_audit |
| `apps/web` cockpit RTL | Premium analysis shell | **KEEP** | Identity + UX | Wire new states (risky markets, buyer categories); no wholesale redesign |

## Dependency graph (impact)

```
create_run → schedule_pipeline → orchestrator
                ↓
         resolve_providers → trade (WITS→research→comtrade?) + search + llm
                ↓
         markets_json + report → UI SSE
select_country / buyers → search_buyers → BuyerSearchRow
feasibility POST → recompute
```

Agentic target inserts: **memory lookup → plan → tools → claims → score → emit**, with human gate before buyers.

## Known risks

- No paid keys in this environment → adapters must fail honestly / stub.
- WITS is sector-only; HS6 bilateral not free → scoring must refuse false confidence.
- ThreadPool “jobs” are process-local; lease + DB checkpoints mitigate restart (already partially done).
