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


# Per-run caps. The global row is a fleet ceiling, not a copy of these defaults.
RUN_MODEL_CALLS = 12
RUN_SEARCH_QUERIES = 20
RUN_PAGES = 15
RUN_RETRIES = 2
RUN_WALL_SECONDS = 180


def ensure_run_budget(db: Session, run_id: str) -> AgentBudget:
    row = db.scalar(
        select(AgentBudget).where(AgentBudget.scope == "run", AgentBudget.scope_id == run_id)
    )
    if row:
        return row
    global_row = ensure_global_budget(db)
    row = AgentBudget(
        scope="run",
        scope_id=run_id,
        max_model_calls=min(RUN_MODEL_CALLS, global_row.max_model_calls),
        max_search_queries=min(RUN_SEARCH_QUERIES, global_row.max_search_queries),
        max_pages=min(RUN_PAGES, global_row.max_pages),
        max_retries=min(RUN_RETRIES, global_row.max_retries),
        max_wall_seconds=min(RUN_WALL_SECONDS, global_row.max_wall_seconds),
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
    row = AgentBudget(
        scope="global",
        max_model_calls=400,
        max_search_queries=400,
        max_pages=300,
        max_retries=2,
        max_wall_seconds=180,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _limit_message(kind: str, *, fleet: bool) -> str:
    scope = "کلی" if fleet else "این مأموریت"
    if kind == "model":
        return f"سقف فراخوانی مدل برای {scope} تمام شد."
    if kind == "search":
        return f"سقف جست‌وجوی وب برای {scope} تمام شد."
    if kind == "page":
        return f"سقف خواندن صفحه برای {scope} تمام شد."
    raise ValueError(f"unknown budget kind {kind}")


def _used(budget: AgentBudget, kind: str) -> int:
    if kind == "model":
        return budget.model_calls_used
    if kind == "search":
        return budget.search_queries_used
    if kind == "page":
        return budget.pages_used
    raise ValueError(f"unknown budget kind {kind}")


def _cap(budget: AgentBudget, kind: str) -> int:
    if kind == "model":
        return budget.max_model_calls
    if kind == "search":
        return budget.max_search_queries
    if kind == "page":
        return budget.max_pages
    raise ValueError(f"unknown budget kind {kind}")


def _add_used(budget: AgentBudget, kind: str, units: int) -> None:
    if kind == "model":
        budget.model_calls_used += units
    elif kind == "search":
        budget.search_queries_used += units
    elif kind == "page":
        budget.pages_used += units
    else:
        raise ValueError(f"unknown budget kind {kind}")
    budget.updated_at = datetime.now(timezone.utc)


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
    """Reserve budget and persist the audit before the caller performs the side effect."""

    if units <= 0:
        return
    targets: list[AgentBudget] = [budget]
    if budget.scope != "global":
        targets.append(ensure_global_budget(db))
    # Model, search, and page counts are recorded. They do not stop a run.
    for target in targets:
        _add_used(target, kind, units)
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


def guarded_model_call(db: Session, run_id: str, purpose: str, fn, *, provider_id: str = "llm"):
    """Consume the model budget, then invoke fn. Key presence never reaches fn by itself."""

    budget = ensure_run_budget(db, run_id)
    consume(
        db,
        budget,
        kind="model",
        units=1,
        run_id=run_id,
        provider_id=provider_id,
        tool_name=purpose,
        detail_fa=f"رزرو بودجه پیش از فراخوانی مدل ({purpose})",
    )
    return fn()
