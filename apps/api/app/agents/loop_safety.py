"""Operational safety for the research loop. These are not research-depth caps."""

from __future__ import annotations

DEFAULT_SAFETY = {
    "max_consecutive_invalid": 3,
    "max_repeated_actions": 3,
    "max_fruitless_searches": 3,
    "max_runtime_seconds": 1800,
    "max_run_tokens": 200_000,
}


def operational_stop(
    *,
    invalid_streak: int,
    repeated: int,
    elapsed_seconds: float,
    tokens: int,
    limits: dict[str, int],
    cancelled: bool,
) -> str | None:
    if cancelled:
        return "cancelled"

    def cap(key: str) -> int:
        if key not in limits or limits.get(key) is None:
            return int(DEFAULT_SAFETY[key])
        return int(limits[key])

    invalid_cap = cap("max_consecutive_invalid")
    if invalid_cap > 0 and invalid_streak >= invalid_cap:
        return "consecutive_invalid"
    repeated_cap = cap("max_repeated_actions")
    if repeated_cap > 0 and repeated > repeated_cap:
        return "no_progress"
    runtime = cap("max_runtime_seconds")
    if runtime > 0 and elapsed_seconds >= runtime:
        return "runtime"
    token_cap = cap("max_run_tokens")
    if token_cap > 0 and tokens >= token_cap:
        return "spending"
    return None


def action_signature(action: str, tool: str | None, args: dict) -> str:
    import json

    return json.dumps({"action": action, "tool": tool or "", "args": args}, sort_keys=True, ensure_ascii=False)
