"""Normalize provider chat payloads into JSON values. No secrets and no invented fields."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("nova.llm")

_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.I)


@dataclass
class ChatOutcome:
    content: str = ""
    finish_reason: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    truncated: bool = False
    cost: float | None = None
    provider_name: str = ""
    served_model: str = ""
    error_category: str = ""
    http_status: int | None = None


def _usage(payload: dict) -> dict[str, int]:
    raw = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    out: dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = raw.get(key)
        if isinstance(value, int):
            out[key] = value
    cost = raw.get("cost")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        out["cost_micros"] = int(float(cost) * 1_000_000)
    return out


def message_text(message: Any) -> tuple[str, str]:
    """Return (decision text, tool-call arguments). Reasoning parts are ignored."""

    if not isinstance(message, dict):
        return "", ""
    tool_calls = message.get("tool_calls") or []
    arguments = ""
    if isinstance(tool_calls, list) and tool_calls:
        fn = (tool_calls[0] or {}).get("function") if isinstance(tool_calls[0], dict) else None
        if isinstance(fn, dict) and isinstance(fn.get("arguments"), str):
            arguments = fn["arguments"]
    content = message.get("content")
    if isinstance(content, str):
        return content, arguments
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") in {"reasoning", "thinking"} or part.get("thought") is True:
                continue
            text = part.get("text") or part.get("content")
            if isinstance(text, str) and text.strip():
                parts.append(text)
        return "\n".join(parts), arguments
    return "", arguments


def parse_chat_completion(payload: Any, *, http_status: int = 200) -> ChatOutcome:
    outcome = ChatOutcome(http_status=http_status)
    if not isinstance(payload, dict):
        outcome.error_category = "malformed"
        return outcome
    if payload.get("error"):
        outcome.error_category = "provider_error"
        return outcome
    outcome.usage = _usage(payload)
    if "cost_micros" in outcome.usage:
        outcome.cost = outcome.usage["cost_micros"] / 1_000_000
    outcome.served_model = str(payload.get("model") or "")
    provider = payload.get("provider")
    if isinstance(provider, str):
        outcome.provider_name = provider
    elif isinstance(provider, dict):
        outcome.provider_name = str(provider.get("name") or provider.get("id") or "")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        outcome.error_category = "empty"
        return outcome
    choice = choices[0]
    outcome.finish_reason = str(choice.get("finish_reason") or "")
    outcome.truncated = outcome.finish_reason in {"length", "max_tokens"}
    text, arguments = message_text(choice.get("message"))
    if arguments.strip() and (not text.strip() or '"action"' in arguments):
        outcome.content = arguments.strip()
    else:
        outcome.content = text
    if not outcome.content.strip():
        outcome.error_category = "truncated" if outcome.truncated else "empty"
    return outcome


def _balanced_json(text: str) -> Any | None:
    start = None
    for index, char in enumerate(text):
        if char in "{[":
            start = index
            break
    if start is None:
        return None
    opening = text[start]
    closing = "}" if opening == "{" else "]"
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                snippet = text[start : index + 1]
                try:
                    return json.loads(snippet)
                except json.JSONDecodeError:
                    snippet = re.sub(r",\s*([}\]])", r"\1", snippet)
                    try:
                        return json.loads(snippet)
                    except json.JSONDecodeError:
                        return None
    return None


def extract_json_value(text: str) -> Any | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    fence = _FENCE.search(raw)
    if fence:
        fenced = fence.group(1).strip()
        try:
            return json.loads(fenced)
        except json.JSONDecodeError:
            found = _balanced_json(fenced)
            if found is not None:
                return found
    return _balanced_json(raw)


def log_call(
    *,
    model: str,
    method: str,
    http_status: int | None,
    finish_reason: str,
    usage: dict[str, int],
    truncated: bool,
    category: str,
    provider_name: str,
) -> None:
    logger.info(
        "llm_call model=%s method=%s http=%s finish=%s prompt_tokens=%s completion_tokens=%s truncated=%s category=%s provider=%s",
        model,
        method,
        http_status,
        finish_reason,
        usage.get("prompt_tokens", 0),
        usage.get("completion_tokens", 0),
        truncated,
        category,
        provider_name or "-",
    )
