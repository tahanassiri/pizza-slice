"""Source credibility heuristics — never treat directory/seller SEO as authoritative trade stats."""

from __future__ import annotations

from urllib.parse import urlparse

from app.agents.tool_contracts import ToolResult

TRUSTED_PUBLISHER_HINTS = (
    "wikipedia.org",
    "worldbank.org",
    "wto.org",
    "fao.org",
    "oecd.org",
    "europa.eu",
    "gov",
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
    score = 0.4
    notes = []
    if any(h in host for h in TRUSTED_PUBLISHER_HINTS):
        score = 0.75
        notes.append("دامنهٔ رسمی/سازمان بین‌المللی یا دانشنامه")
    if any(h in host for h in LOW_TRUST):
        score = 0.15
        notes.append("دایرکتوری/شبکه اجتماعی — اعتبار تجاری پایین")
    if host.endswith(".gov") or ".gov." in host:
        score = max(score, 0.8)
        notes.append("دامنه دولتی")
    level = "high" if score >= 0.7 else "medium" if score >= 0.45 else "low"
    return ToolResult(
        tool="assess_credibility",
        ok=True,
        message_fa=f"اعتبار منبع: {level}",
        data={
            "url": url,
            "host": host,
            "score": score,
            "level": level,
            "notes_fa": notes,
            "title": title,
            "publisher": publisher,
        },
    )


def cross_check_claims(claims: list[dict]) -> ToolResult:
    """Flag contradictions when two claims mention conflicting years/numbers crudely."""
    conflicts: list[str] = []
    years = []
    for c in claims:
        stmt = str(c.get("statement") or "")
        for y in re_years(stmt):
            years.append((y, stmt[:80], c.get("source_url")))
    # same topic different years → soft conflict note
    uniq = sorted({y for y, _, _ in years})
    if len(uniq) >= 2:
        conflicts.append(
            f"سال‌های متفاوت در شواهد دیده شد: {', '.join(map(str, uniq[:4]))} — نیاز به تفکیک دوره"
        )
    return ToolResult(
        tool="cross_check",
        ok=True,
        message_fa=f"{len(conflicts)} تعارض احتمالی ثبت شد." if conflicts else "تعارض آشکاری یافت نشد.",
        data={"conflicts": conflicts, "claim_count": len(claims)},
    )


def re_years(text: str) -> list[int]:
    import re

    out = []
    for m in re.finditer(r"\b(19|20)\d{2}\b", text):
        out.append(int(m.group(0)))
    return out
