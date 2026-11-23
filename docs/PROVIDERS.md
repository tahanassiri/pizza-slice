# Providers (architecture correction)

## What drives research
- **Active LLM** (admin model picker + per-version encrypted key) is the research decision-maker.
- **Free web tools** (Wikipedia OpenSearch + DuckDuckGo HTML) discover sources dynamically — no API key.
- **Saved key ≠ Verified connection.** Test connection is separate from “key saved”.

## Removed as mandatory integrations
Tavily, Exa, WITS, and UN Comtrade are **not** required, configured, or advertised as mandatory admin key fields.
Legacy DB rows (if present) are soft-disabled. Library code under `trade_data/` may remain for optional experiments but is **not** on the agent critical path.

## Budgets
Server-enforced before tool calls via `AgentBudget` / `/api/admin/budgets`.
