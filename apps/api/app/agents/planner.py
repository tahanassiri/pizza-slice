"""Product-specific research plan (bounded, deterministic heuristics + optional LLM later)."""

from __future__ import annotations

from app.agents.tool_contracts import ResearchPlan

# Seed candidate pools by product family — not ranked winners
_FOOD_CANDIDATES = ["AE", "TR", "DE", "IN", "IQ", "RU", "CN"]
_INDUSTRIAL_CANDIDATES = ["TR", "AE", "DE", "CN", "IN", "RU", "IT"]


def build_research_plan(*, product: str, hs6: str | None, origin: str) -> ResearchPlan:
    p = product.lower()
    industrial = any(
        k in p
        for k in (
            "steel",
            "machine",
            "polymer",
            "chemical",
            "فولاد",
            "پلیمر",
            "شیمیایی",
            "ماشین",
        )
    )
    candidates = list(_INDUSTRIAL_CANDIDATES if industrial else _FOOD_CANDIDATES)
    questions = [
        f"تقاضای واردات «{product}» در بازارهای کاندید با چه دامنه داده‌ای (HS6 در برابر گروه) قابل استناد است؟",
        "محدودیت قانونی/استاندارد ورود از ایران برای این کالا چیست؟",
        "رقبا و کانال توزیع عمده کدام‌اند؟",
        "مسیر پرداخت، بیمه و حمل برای صادرکننده ایرانی چه قیودی دارد؟",
        "دغدغه واردکننده مقصد برای همین کالا چیست؟",
    ]
    if hs6:
        questions.insert(0, f"آیا کد HS {hs6} با ماهیت «{product}» هم‌خوان است؟")
    else:
        questions.insert(0, f"کد HS دقیق «{product}» چیست و آیا ابهام تعیین‌کننده دارد؟")

    tools = ["read_memory", "get_trade_stats", "search_web", "research_regulations", "research_logistics"]
    return ResearchPlan(
        questions=questions,
        candidate_countries=candidates,
        tools_needed=tools,
        notes_fa=(
            f"برنامه تحقیق برای «{product}» از مبدأ {origin}"
            + (f" (HS={hs6})" if hs6 else " (HS نامشخص)")
            + (" — خانواده صنعتی" if industrial else " — خانواده غذایی/کشاورزی")
        ),
    )
