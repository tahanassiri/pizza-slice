"""Market research entry — delegates to LLM-driven decision loop."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from sqlalchemy.orm import Session

from app.agents.decision_loop import run_decision_loop
from app.models.entities import Run
from app.tools.executor import ToolExecutor

EmitFn = Callable[..., Awaitable[Any]]


async def run_market_research(
    db: Session,
    run: Run,
    executor: ToolExecutor,
    emit: EmitFn,
) -> dict[str, Any]:
    return await run_decision_loop(db, run, executor, emit)
