"""Strict decision schema and local validation. Missing fields are not invented."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.agents.llm_decide import TOOL_ARG_SCHEMA, AgentAction
from app.agents.policy import ALLOWED_TOOLS

MINIMAL_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
}

_NULLABLE_STRING = {"type": ["string", "null"]}

AGENT_ACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "action": {
            "type": "string",
            "enum": ["call_tool", "conclude", "ask_user", "change_strategy", "verify_conflict"],
        },
        "tool": _NULLABLE_STRING,
        "source_id": _NULLABLE_STRING,
        "args_json": {"type": "string"},
        "rationale_fa": {"type": "string"},
        "stop_reason": _NULLABLE_STRING,
        "market_proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "country_code": {"type": "string"},
                    "recommendation": {"type": "string", "enum": ["recommended", "risky", "watch"]},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "data_scope": {"type": "string", "enum": ["hs6", "product_family", "sector", "total", "qualitative"]},
                    "risks": {"type": "array", "items": {"type": "string"}},
                    "criteria": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "criterion": {
                                    "type": "string",
                                    "enum": ["demand", "access", "legal", "logistics", "payment", "competition"],
                                },
                                "evidence_ids": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["criterion", "evidence_ids"],
                        },
                    },
                },
                "required": ["country_code", "recommendation", "evidence_ids", "data_scope", "risks", "criteria"],
            },
        },
        "unknowns": {"type": "array", "items": {"type": "string"}},
        "conflicts": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "action",
        "tool",
        "source_id",
        "args_json",
        "rationale_fa",
        "stop_reason",
        "market_proposals",
        "unknowns",
        "conflicts",
    ],
}

_REQUIRED_TOOL_ARGS = {
    "search_web": ("query",),
    "fetch_page": ("url",),
    "fetch_source": ("source_id",),
    "extract_claims": ("url",),
    "verify_company": ("company_name", "country"),
    "classify_product": ("product",),
}

SYNTHESIS_ACTIONS = ("conclude", "ask_user")


def decision_json_schema(context: dict[str, Any]) -> dict[str, Any]:
    if context.get("decision_mode") != "synthesis":
        return AGENT_ACTION_JSON_SCHEMA
    properties = AGENT_ACTION_JSON_SCHEMA["properties"]
    return {
        **AGENT_ACTION_JSON_SCHEMA,
        "properties": {
            **properties,
            "action": {**properties["action"], "enum": list(SYNTHESIS_ACTIONS)},
        },
    }


def prepare_decision_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = dict(data)
    if "args" not in payload and isinstance(payload.get("args_json"), str):
        try:
            parsed = json.loads(payload["args_json"] or "{}")
        except json.JSONDecodeError:
            parsed = None
        payload["args"] = parsed if isinstance(parsed, dict) else {}
    elif not isinstance(payload.get("args"), dict):
        payload["args"] = {}
    payload.pop("args_json", None)
    if payload.get("tool") == "fetch_source" and payload.get("source_id") is not None:
        payload["args"] = {**payload["args"], "source_id": payload["source_id"]}
    return payload


def validate_decision(data: Any) -> tuple[AgentAction | None, str]:
    """Return an action or a short validation note. Never fill in missing decisions."""

    if not isinstance(data, dict):
        return None, "پاسخ JSON شیء نبود."
    payload = prepare_decision_payload(data)
    try:
        action = AgentAction.model_validate(payload)
    except ValidationError as exc:
        bits = []
        for item in exc.errors()[:4]:
            loc = ".".join(str(part) for part in item.get("loc") or [])
            bits.append(f"{loc}: {item.get('type')}")
        return None, "طرح تصمیم نخواند (" + ", ".join(bits) + ")."
    if action.action == "blocked":
        return None, "اقدام blocked از مدل پذیرفته نمی‌شود."
    if action.action == "call_tool":
        if not action.tool or action.tool not in ALLOWED_TOOLS:
            return None, "ابزار تصمیم در فهرست مجاز نیست."
        missing = [
            key for key in _REQUIRED_TOOL_ARGS.get(action.tool, ())
            if not isinstance(action.args.get(key), str) or not action.args[key].strip()
        ]
        if missing:
            return None, "آرگومان ابزار کم است: " + ", ".join(missing) + "."
        if action.tool not in TOOL_ARG_SCHEMA and action.tool not in ALLOWED_TOOLS:
            return None, "ابزار تصمیم شناخته نشد."
    action.decision_source = "llm"
    return action, ""
