"""Choose a structured-output method for one model. Never selects a different model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

OUTPUT_CHAIN = ("json_schema", "json_object", "function", "prompt")


@dataclass
class StructuredResult:
    ok: bool = False
    content: str = ""
    data: Any = None
    method: str = "prompt"
    category: str = "empty"
    finish_reason: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    truncated: bool = False
    raw_text: str = ""
    provider_name: str = ""
    http_status: int | None = None
    message_fa: str = ""


def select_output_method(parameters: list[str] | set[str] | None) -> str:
    names = {str(item).lower() for item in (parameters or [])}
    if "structured_outputs" in names:
        return "json_schema"
    if "response_format" in names:
        return "json_object"
    if "tools" in names:
        return "function"
    return "prompt"


def next_method(method: str) -> str | None:
    if method not in OUTPUT_CHAIN:
        return "prompt"
    index = OUTPUT_CHAIN.index(method)
    if index + 1 >= len(OUTPUT_CHAIN):
        return None
    return OUTPUT_CHAIN[index + 1]


def output_budget(purpose: str, model_limit: int | None = None) -> tuple[int, int]:
    table = {
        "capability-basic": (512, 2048),
        "capability-decision": (2048, 8192),
        "decide": (4096, 8192),
        "classify": (512, 2048),
    }
    initial, ceiling = table.get(purpose, (2048, 8192))
    if model_limit and model_limit > 0:
        ceiling = min(ceiling, model_limit)
        initial = min(initial, ceiling)
    return max(initial, 16), max(ceiling, 16)


def parameter_rejected(status: int, body: str) -> bool:
    if status not in {400, 404, 422}:
        return False
    text = (body or "").lower()
    needles = (
        "response_format",
        "structured",
        "json_schema",
        "require_parameters",
        "requested parameters",
        "no endpoints",
        "not support",
        "unsupported",
        "unknown parameter",
        "invalid parameter",
        "plugins",
        "response-healing",
        "tool choice",
        "tools",
    )
    return any(needle in text for needle in needles)


def request_body(
    *,
    model: str,
    prompt: str,
    method: str,
    schema: dict | None,
    schema_name: str,
    max_tokens: int,
    correction: str = "",
    router_controls: bool = True,
) -> dict:
    content = prompt
    if correction:
        content = (
            prompt
            + "\n\nThe previous JSON failed validation: "
            + correction[:400]
            + "\nReturn only the corrected JSON object."
        )
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    if method == "json_schema" and schema:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        }
        if router_controls:
            body["provider"] = {"require_parameters": True}
            body["plugins"] = [{"id": "response-healing"}]
    elif method == "json_object":
        body["response_format"] = {"type": "json_object"}
        if router_controls:
            body["provider"] = {"require_parameters": True}
            body["plugins"] = [{"id": "response-healing"}]
    elif method == "function" and schema:
        body["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": schema_name,
                    "strict": True,
                    "parameters": schema,
                },
            }
        ]
        body["tool_choice"] = {"type": "function", "function": {"name": schema_name}}
        if router_controls:
            body["provider"] = {"require_parameters": True}
    return body
