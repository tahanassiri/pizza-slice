# Agentic Progress Log

## Phase 0 — Inventory
- **Implemented:** Gap map, plan, branch from main `d6b757e`
- **Tests:** baseline then expanded
- **Pass-Fail:** PASS
- **Files:** `docs/AGENTIC_GAP_MAP.md`, `AGENTIC_IMPLEMENTATION_PLAN.md`, `AGENTIC_PROGRESS.md`
- **Remaining:** —

## Phase 1 — Agent infra + memory
- **Implemented:** tasks/leases, knowledge+TTL, evidence/claims, budgets, tool executor, migration 003
- **Tests:** `test_agentic_core.py`
- **Pass-Fail:** PASS
- **Files:** `app/{agents,tools,knowledge,jobs,evidence}/`, `003_agentic_memory.py`
- **Remaining:** multi-node singleflight

## Phase 2 — Market Research
- **Implemented:** agentic pipeline, plan, trade tool, deterministic scorer, recommended+risky, memory reuse, SSE payloads
- **Tests:** scorer + pipeline integrations
- **Pass-Fail:** PASS
- **Files:** `research_runner.py`, `market_scorer.py`, `orchestrator_controller.py`
- **Remaining:** richer official legal adapters

## Phase 3 — Buyers
- **Implemented:** select gate, verify_company, categories, per-card SSE, company_profiles
- **Tests:** seller rejection + buyer background
- **Pass-Fail:** PASS
- **Files:** `buyer_runner.py`, `verify_company.py`, `runs.py`
- **Remaining:** local-language query packs

## Phase 4 — Economics
- **Implemented:** cost status, break-even, sensitivity, no fabricated profit
- **Tests:** feasibility suite + §9.10
- **Pass-Fail:** PASS
- **Files:** `feasibility_calc.py`, contracts
- **Remaining:** live quote adapters

## Phase 5 — UI/Admin
- **Implemented:** recommended vs risky UI; admin budgets/knowledge/usage
- **Tests:** web typecheck/lint/build PASS
- **Pass-Fail:** PASS
- **Files:** `MarketComparison.tsx`, `admin.py`
- **Remaining:** admin budget UI widgets

## Phase 6 — Hardening + §9 acceptance
- **Implemented:** SSRF guards, budget enforce, lease recovery, §9.1–15 automated tests, rate-limit test isolation
- **Tests:** **83 passed** (`pytest`); web typecheck/lint/build PASS; Playwright NOT_RUN (no dep)
- **Pass-Fail:** PASS (automated); VPS deploy **BLOCKED** (SSH auth)
- **Files:** `tests/test_section9_acceptance.py`, `tests/conftest.py`
- **Remaining:** VPS deploy when SSH credential available

## Architecture correction — LLM decision loop (post Phase 6)
- **Implemented:** `decision_loop` + `llm_decide`; removed mandatory Tavily/Exa/WITS/Comtrade admin; free_web tools; planner country pools cleared; memory period="" fix; buyer SSE commit-before-publish; lease → interrupted→queued; Tests A–L
- **Tests:** **93 passed**; Test L live Wikipedia+DDG **PASS**; web typecheck/lint/build **PASS**; Playwright smoke **PASS** (`1 passed (7.0s)`)
- **Pass-Fail:** Automated + e2e PASS; VPS **BLOCKED**; PR **NOT READY**
- **Files:** `agents/{decision_loop,llm_decide}.py`, `tools/{free_web,extract,credibility}.py`, `test_architecture_correction.py`, `apps/web/e2e/*`, admin/providers/docs
- **Report:** Project store `docs/agentic-architecture-correction.md` (A–N + matrix; Playwright evidence)
- **Remaining:** VPS when SSH works

## Playwright e2e smoke
- **Implemented:** `@playwright/test` ^1.65.1; chromium + deps installed; `e2e/smoke.spec.ts` (RTL home → start analysis → cockpit)
- **Run:** `cd apps/web && npm run test:e2e` → **1 passed (7.0s)** against local stub API
- **Docs:** `apps/web/e2e/README.md` (live API default; `E2E_DATA_SOURCE=mock` fixture path)

## §9 Acceptance matrix
| # | Result | Test |
|---|--------|------|
| 1 | PASS | `test_s9_1_research_plan_and_usage_audit` |
| 2 | PASS | `test_s9_2_different_products_distinct_memory_and_sector_label` |
| 3 | PASS | `test_s9_3_reference_year_on_markets_and_stale_flag` |
| 4 | PASS | `test_s9_4_memory_hit_surfaces_via_events` |
| 5 | PASS | `test_s9_5_stub_providers_no_invented_markets_or_buyers` |
| 6 | PASS | `test_s9_6_unknown_criteria_not_hidden` |
| 7 | PASS | `test_s9_7_recommended_and_risky_split` |
| 8 | PASS | `test_s9_8_buyers_gate_requires_selection` |
| 9 | PASS | `test_s9_9_seller_and_title_only_not_verified` |
| 10 | PASS | `test_s9_10_calculator_scenarios_and_missing` |
| 11 | PASS | `test_s9_11_sse_resume_and_lease_recovery` |
| 12 | PASS | `test_s9_12_privacy_and_prompt_injection_guard` |
| 13 | PASS | `test_s9_13_budget_enforced_server_side` |
| 14 | PASS* | pytest+typecheck+lint+build; Playwright NOT_RUN |
| 15 | PASS | docs + `agentic-final-report.md` |
