"""Phase gates. They reject an unfinished stage; they do not invent the next research decision."""

from __future__ import annotations

from app.tools.extract import country_code

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

FRUITLESS_SEARCH_FEEDBACK = (
    "جست‌وجوهای اخیر منبع تازه و قابل بررسی اضافه نکردند. "
    "جست‌وجوی هم‌معنا را تکرار نکنید. منبع نخوانده یا نشانی عمومی معتبر را مستقیماً باز کنید، "
    "فرضیهٔ متفاوتی را بررسی کنید یا با شواهد موجود جمع‌بندی کنید."
)

UNREAD_SOURCE_FEEDBACK = (
    "منابع کشف‌شده هنوز خوانده نشده‌اند و ادعای استخراج‌شده‌ای در CONTEXT.evidence نیست. "
    "نتیجه جست‌وجو شاهد تأییدشده نیست. یک نشانی را با fetch_page انتخاب کنید."
)

ALREADY_PROCESSED_FEEDBACK = (
    "این منبع قبلاً بررسی شده است. استخراج دوباره انجام نشد. "
    "یک منبع نخوانده را انتخاب کنید یا change_strategy را صدا بزنید."
)


def shortlist_evidence(rows: list[dict], candidates: dict, origin: str, hs6: str | None) -> set[str]:
    """Find evidence for a comparison without choosing or ranking markets."""
    origin_code = country_code(origin)
    by_country = {
        code: {ref for item in candidate.get("criteria", []) if item["criterion"] == "demand"
               for ref in item["evidence_ids"]}
        for code, candidate in candidates.items()
    }
    for row in rows:
        trade = row.get("trade") or {}
        destination = row.get("country")
        if not (destination and destination != origin_code and hs6 and row.get("hs_scope") == hs6 and trade.get("year")):
            continue
        if not (trade.get("trade_value") or trade.get("quantity")):
            continue
        if (trade.get("flow") == "import" and trade.get("reporter") == destination) or (
            origin_code and trade.get("flow") == "export"
            and trade.get("reporter") == origin_code and trade.get("partner") == destination
        ):
            by_country.setdefault(destination, set()).add(row["id"])
    priority = {
        row["id"]: ((row.get("trade") or {}).get("partner") != "WLD", position)
        for position, row in enumerate(rows)
    }
    supported = [available for refs in by_country.values() if (available := refs & priority.keys())]
    return {min(refs, key=priority.__getitem__) for refs in supported} if len(supported) >= 2 else set()


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


def unread_sources_block_conclude(observations: list[dict] | None, evidence_count: int) -> str | None:
    if evidence_count:
        return None
    if not any(row.get("status") == "unread" for row in observations or []):
        return None
    return UNREAD_SOURCE_FEEDBACK


def buyer_research_blocked(tool: str | None, selected_country: str | None) -> str | None:
    if tool not in BUYER_TOOLS:
        return None
    if (selected_country or "").strip():
        return None
    return BUYER_GATE_FEEDBACK
