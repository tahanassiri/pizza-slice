"""Durable stage lifecycle for agentic runs."""

from __future__ import annotations

from typing import Literal

Stage = Literal[
    "intake",
    "product_classify",
    "memory_lookup",
    "research_plan",
    "market_research",
    "market_rank",
    "await_market_select",
    "buyer_research",
    "feasibility",
    "report",
]

Status = Literal[
    "queued",
    "running",
    "partial",
    "needs_input",
    "completed",
    "failed",
    "cancelled",
    "interrupted",
]

# Public AnalysisPhase values used by existing UI (subset mapped)
UI_PHASE_MAP: dict[str, str] = {
    "intake": "intake",
    "product_classify": "product_classify",
    "memory_lookup": "search",
    "research_plan": "search",
    "market_research": "trade_stats",
    "market_rank": "market_compare",
    "await_market_select": "conclude",
    "buyer_research": "buyers",
    "feasibility": "feasibility",
    "report": "report",
}

_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"running", "cancelled", "failed", "interrupted"}),
    "running": frozenset({"partial", "needs_input", "completed", "failed", "cancelled", "interrupted"}),
    "partial": frozenset({"running", "completed", "failed", "needs_input", "cancelled"}),
    "needs_input": frozenset({"running", "cancelled", "failed"}),
    "completed": frozenset(),
    "failed": frozenset({"queued", "running"}),  # retry
    "cancelled": frozenset(),
    "interrupted": frozenset({"queued", "running", "failed"}),
}


def can_transition(current: str, nxt: str) -> bool:
    return nxt in _TRANSITIONS.get(current, frozenset())


def assert_transition(current: str, nxt: str) -> None:
    if current == nxt:
        return
    if not can_transition(current, nxt):
        raise ValueError(f"illegal status transition {current} → {nxt}")


def ui_phase(stage: str) -> str:
    return UI_PHASE_MAP.get(stage, stage)
