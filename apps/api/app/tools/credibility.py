"""Source credibility labels. Levels are qualitative — missing trust is unknown, not a filler score."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.agents.tool_contracts import ToolResult

TRUSTED_PUBLISHER_HINTS = (
    "wikipedia.org",
    "worldbank.org",
    "wto.org",
    "fao.org",
    "oecd.org",
    "europa.eu",
    "un.org",
    "imf.org",
)
LOW_TRUST = (
    "alibaba.com",
    "made-in-china.com",
    "indiamart.com",
    "facebook.com",
    "pinterest.com",
)


def assess_credibility(*, url: str, title: str = "", publisher: str = "") -> ToolResult:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    level = "unknown"
    notes: list[str] = []
    if any(hint in host for hint in TRUSTED_PUBLISHER_HINTS):
        level = "high"
        notes.append("دامنهٔ رسمی/سازمان بین‌المللی یا دانشنامه")
    if any(hint in host for hint in LOW_TRUST):
        level = "low"
        notes.append("دایرکتوری/شبکه اجتماعی — اعتبار تجاری پایین")
    if host.endswith(".gov") or ".gov." in host:
        level = "high"
        notes.append("دامنه دولتی")
    if not notes:
        notes.append("سطح اعتماد از روی دامنه معلوم نیست")
    return ToolResult(
        tool="assess_credibility",
        ok=True,
        message_fa=f"اعتبار منبع: {level}",
        data={
            "url": url,
            "host": host,
            "score": None,
            "level": level,
            "notes_fa": notes,
            "title": title,
            "publisher": publisher,
        },
    )


def cross_check_claims(claims: list[dict]) -> ToolResult:
    """Record period disagreements. Do not collapse them into a confidence number."""

    conflicts: list[str] = []
    years: list[tuple[int, str, object]] = []
    for claim in claims:
        statement = str(claim.get("statement") or "")
        for year in re_years(statement):
            years.append((year, statement[:80], claim.get("source_url")))
    unique_years = sorted({year for year, _, _ in years})
    if len(unique_years) >= 2:
        conflicts.append(
            "سال‌های متفاوت در شواهد دیده شد: "
            + ", ".join(str(year) for year in unique_years[:4])
            + " — اختلاف دوره حل‌نشده مانده است"
        )
    return ToolResult(
        tool="cross_check",
        ok=True,
        message_fa=f"{len(conflicts)} تعارض احتمالی ثبت شد." if conflicts else "تعارض آشکاری یافت نشد.",
        data={"conflicts": conflicts, "claim_count": len(claims)},
    )


def re_years(text: str) -> list[int]:
    found: list[int] = []
    for match in re.finditer(r"\b(19|20)\d{2}\b", text):
        found.append(int(match.group(0)))
    return found
