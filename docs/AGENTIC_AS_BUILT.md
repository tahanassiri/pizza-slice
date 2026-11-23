# Agentic as-built (summary)

```
UI (RTL cockpit) ──SSE/REST──► FastAPI runs/admin
                                │
                    orchestrator_controller
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
        ToolExecutor      KnowledgeRepo      ResearchTask lease
              │                 │
    search/trade/fetch/verify/calc
              │
        claims + market_assessments + company_profiles
              │
        deterministic market_scorer → markets_json / report
              │
        human select_country → buyer_runner (gated)
              │
        feasibility_calc (deterministic)
```

**Dev runbook:** set `PROVIDER_MODE=auto` or `stub`; configure model/search keys in admin; budgets via `PUT /api/admin/budgets`. SQLite default. Do not push secrets. VPS deploy out of scope for this mission.

**Migrations:** `001` → `002` → `003_agentic_memory`. `init_db()` also `create_all` for fresh SQLite.
