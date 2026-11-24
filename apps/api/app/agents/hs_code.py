"""HS6 parsing and evidence checks. No product is special-cased."""

from __future__ import annotations

import re

from app.providers.response_norm import extract_json_value

_HS_TOKEN = re.compile(r"(?<!\d)(\d{4})[.](\d{2})(?!\d)|(?<!\d)(\d{6})(?!\d)")

HS_JSON_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"hs6": {"type": ["string", "null"]}},
    "required": ["hs6"],
}
_HS_FIELD = ("hs6", "hs_code", "code")


def hs_codes_in_text(text: str) -> list[str]:
    found: list[str] = []
    for match in _HS_TOKEN.finditer(text or ""):
        code = (match.group(1) + match.group(2)) if match.group(1) else match.group(3)
        if code not in found:
            found.append(code)
    return found


def parse_hs6(text: str) -> str | None:
    """Read one HS6 from model text. A leading zero is kept. Digits are not concatenated."""

    raw = text or ""
    data = extract_json_value(raw)
    if isinstance(data, dict):
        for key in _HS_FIELD:
            value = data.get(key)
            if isinstance(value, str) and re.fullmatch(r"\d{6}", value.strip()):
                return value.strip()
            if isinstance(value, int) and re.fullmatch(r"\d{6}", str(value)) and str(value) in raw:
                return str(value)
    codes = hs_codes_in_text(raw)
    return codes[0] if codes else None


def accept_hs_evidence(
    *,
    hypothesis: str | None,
    confirmed: str | None,
    source_text: str,
    search_ok: bool,
) -> tuple[str | None, str]:
    """Keep a code only when sources support it. A failed search leaves the guess unverified."""

    supported = set(hs_codes_in_text(source_text))
    if not search_ok:
        return (hypothesis, "low") if hypothesis else (None, "unknown")
    if confirmed and confirmed in supported:
        return confirmed, "medium"
    if hypothesis and hypothesis in supported:
        return hypothesis, "medium"
    return None, "unknown"
