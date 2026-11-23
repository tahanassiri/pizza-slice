"""Extract structured claims from untrusted page text — never execute instructions."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.agents.tool_contracts import ToolResult

# Strip common injection patterns from becoming "commands"
_INJECTION = re.compile(
    r"(ignore (all )?(previous|prior) instructions|system\s*:|you are now|"
    r"فرامین قبلی را نادیده|دستور سیستم)",
    re.I,
)


def extract_claims(
    *,
    text: str,
    url: str,
    product: str,
    max_claims: int = 8,
) -> ToolResult:
    raw = (text or "")[:12000]
    sanitized = _INJECTION.sub("[untrusted-text]", raw)
    # Heuristic sentence/claim extraction — LLM may refine later; never invent numbers
    sentences = re.split(r"(?<=[.!?۔؟])\s+", sanitized)
    claims: list[dict] = []
    product_l = product.lower()
    keywords = (
        "export",
        "import",
        "market",
        "tariff",
        "regulation",
        "demand",
        "production",
        "صادرات",
        "واردات",
        "بازار",
        "تعرفه",
        "تقاضا",
    )
    for s in sentences:
        s = s.strip()
        if len(s) < 40 or len(s) > 400:
            continue
        score = sum(1 for k in keywords if k in s.lower())
        if product_l and product_l in s.lower():
            score += 2
        if score < 1:
            continue
        claims.append(
            {
                "statement": s,
                "data_kind": "estimate",
                "confidence": "low",
                "source_url": url,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if len(claims) >= max_claims:
            break

    return ToolResult(
        tool="extract_claims",
        ok=True,
        message_fa=f"{len(claims)} ادعا از متن استخراج شد (نیازمند اعتبارسنجی).",
        data={
            "claims": claims,
            "url": url,
            "injection_sanitized": bool(_INJECTION.search(raw)),
        },
        provenance=[{"url": url, "publisher": "page", "fetched_at": datetime.now(timezone.utc).isoformat()}],
    )
