# Agentic Implementation Plan

## Phases (execute in this mission)

### Phase 0 — Inventory
- Gap map + this plan + progress log
- Baseline pytest green
- Branch `feat/agentic-market-research`

### Phase 1 — Agent infra + memory
**Files:** `app/agents/*`, `app/tools/*`, `app/knowledge/*`, `app/jobs/*`, `app/evidence/*`, models + migration `003`, config budget defaults  
**Tests:** memory isolation/stale, state transitions, budget refuse, tool contract validation

### Phase 2 — Market Research vertical slice
**Files:** `agents/research_runner.py`, `agents/market_scorer.py`, replace `orchestrator.py` entry, extend Market fields  
**Tests:** pistachio vs different food product ≠ identical fabricated ranks; sector labeled; partial on tool fail; golden scorer unit tests

### Phase 3 — Buyer agent + gate
**Files:** `agents/buyer_runner.py`, `tools/verify_company.py`, rewrite buyer path in `runs.py`  
**Tests:** seller false-positive rejected; no search before select; SSE incremental; empty honest

### Phase 4 — Economics
**Files:** `tools/economic_calculator.py` (wrap calc), cost estimate provenance on Feasibility  
**Tests:** math scenarios; missing → no fabricated profit; Incoterm note

### Phase 5 — UI/Admin polish
**Files:** MarketComparison risky section, BuyerCard categories, admin budget display  
**Tests:** typecheck/lint if available; keep Persian RTL

### Phase 6 — Hardening + delivery
- Full pytest + new agent tests
- Delivery doc in store + repo progress
- No VPS deploy

## Design decisions
1. Single in-process worker pool + durable SQL checkpoints (no Redis for MVP).
2. LLM proposes structured actions; tools execute from allowlist only.
3. Deterministic scorer for final market ranks; LLM may suggest weights within bounds.
4. Public knowledge reusable; run private assumptions never promote.
5. Preserve existing REST/SSE contracts; additive optional fields only.
