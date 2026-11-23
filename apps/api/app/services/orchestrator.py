"""Pipeline entrypoints — agentic controller (legacy name kept for tests/imports)."""

from __future__ import annotations

from app.agents.orchestrator_controller import (
    run_agentic_pipeline,
    schedule_agentic_pipeline,
)
from app.providers.registry import resolve_providers

__all__ = ["run_pipeline", "schedule_pipeline", "resolve_providers"]


async def run_pipeline(run_id: str) -> None:
    """Background orchestration — agentic research loop."""
    await run_agentic_pipeline(run_id)


def schedule_pipeline(run_id: str) -> None:
    schedule_agentic_pipeline(run_id)
