"""Server-side budget enforcement for agent tools."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AgentBudget, UsageAudit


class BudgetExceeded(Exception):
    def __init__(self, message_fa: str, code: str = "BUDGET_EXCEEDED"):
        self.message_fa = message_fa
        self.code = code
        super().__init__(message_fa)


def ensure_run_budget(db: Session, run_id: str) -> AgentBudget:
    row = db.scalar(
        select(AgentBudget).where(AgentBudget.scope == "run", AgentBudget.scope_id == run_id)
    )
    if row:
        return row
    # clone from global defaults if present
    global_row = db.scalar(select(AgentBudget).where(AgentBudget.scope == "global").limit(1))
    row = AgentBudget(
        scope="run",
        scope_id=run_id,
        max_model_calls=global_row.max_model_calls if global_row else 12,
        max_search_queries=global_row.max_search_queries if global_row else 20,
        max_pages=global_row.max_pages if global_row else 15,
        max_retries=global_row.max_retries if global_row else 2,
        max_wall_seconds=global_row.max_wall_seconds if global_row else 180,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def ensure_global_budget(db: Session) -> AgentBudget:
    row = db.scalar(select(AgentBudget).where(AgentBudget.scope == "global").limit(1))
    if row:
        return row
    row = AgentBudget(scope="global", updated_at=datetime.now(timezone.utc))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def consume(
    db: Session,
    budget: AgentBudget,
    *,
    kind: str,
    units: int = 1,
    run_id: str | None = None,
    provider_id: str = "system",
    tool_name: str = "",
    ok: bool = True,
    detail_fa: str | None = None,
) -> None:
    if kind == "model":
        if budget.model_calls_used + units > budget.max_model_calls:
            raise BudgetExceeded("سقف فراخوانی مدل برای این مأموریت تمام شد.")
        budget.model_calls_used += units
    elif kind == "search":
        if budget.search_queries_used + units > budget.max_search_queries:
            raise BudgetExceeded("سقف جست‌وجوی وب برای این مأموریت تمام شد.")
        budget.search_queries_used += units
    elif kind == "page":
        if budget.pages_used + units > budget.max_pages:
            raise BudgetExceeded("سقف خواندن صفحه برای این مأموریت تمام شد.")
        budget.pages_used += units
    else:
        raise ValueError(f"unknown budget kind {kind}")

    budget.updated_at = datetime.now(timezone.utc)
    db.add(
        UsageAudit(
            run_id=run_id,
            provider_id=provider_id,
            tool_name=tool_name or kind,
            units=units,
            ok=1 if ok else 0,
            detail_fa=detail_fa,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
