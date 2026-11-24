"""Phase gates. They reject an unfinished stage; they do not invent the next research decision."""

from __future__ import annotations

MARKET_TOOLS = frozenset({"search_web", "fetch_page"})
BUYER_TOOLS = frozenset({"verify_company"})

MARKET_DISCOVERY_FEEDBACK = (
    "کشف بازار هنوز انجام نشده است. search_web را برای بازارهای صادراتی صدا بزنید. "
    "انتخاب کشور مقصد و حافظه خالی پیش‌نیاز نیستند. "
    "قانون ۴ فقط تحقیق گسترده خریدار را تا انتخاب مقصد ممنوع می‌کند."
)

BUYER_GATE_FEEDBACK = (
    "تحقیق خریدار تا وقتی کاربر یک مقصد را انتخاب کند انجام نمی‌شود. "
    "کشف بازار را با search_web ادامه دهید."
)


def market_discovery_attempted(tools_invoked: list[str], tool_trace: list[dict] | None = None) -> bool:
    if any(tool in MARKET_TOOLS for tool in tools_invoked):
        return True
    for item in tool_trace or []:
        if item.get("tool") in MARKET_TOOLS:
            return True
    return False


def premature_market_stop(action: str, tools_invoked: list[str], tool_trace: list[dict] | None = None) -> str | None:
    if action not in {"conclude", "ask_user"}:
        return None
    if market_discovery_attempted(tools_invoked, tool_trace):
        return None
    return MARKET_DISCOVERY_FEEDBACK


def buyer_research_blocked(tool: str | None, selected_country: str | None) -> str | None:
    if tool not in BUYER_TOOLS:
        return None
    if (selected_country or "").strip():
        return None
    return BUYER_GATE_FEEDBACK
