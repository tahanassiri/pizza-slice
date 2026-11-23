"""Product-specific research questions — NO hardcoded country pools."""

from __future__ import annotations

from app.agents.tool_contracts import ResearchPlan


def build_research_plan(*, product: str, hs6: str | None, origin: str) -> ResearchPlan:
    """Seed open questions only. Candidate countries come from evidence, not a fixed pool."""
    questions = [
        f"کدام مقاصد وارداتی برای «{product}» از مبدأ {origin} با شواهد قابل دفاع مطرح‌اند؟",
        "تقاضا و روند با چه دامنه داده‌ای (محصول‌محور در برابر گروهی) قابل استناد است؟",
        "محدودیت قانونی، استاندارد، پرداخت، بیمه و حمل برای همین کالا چیست؟",
        "رقبا و کانال توزیع چیست و دغدغه واردکننده/صادرکننده امروز چیست؟",
    ]
    if hs6:
        questions.insert(0, f"آیا کد HS {hs6} با ماهیت «{product}» هم‌خوان است؟")
    else:
        questions.insert(0, f"کد HS دقیق «{product}» چیست و آیا ابهام تعیین‌کننده دارد؟")

    return ResearchPlan(
        questions=questions,
        candidate_countries=[],  # discovered via research — never seeded from hardcode
        tools_needed=[
            "search_web",
            "fetch_page",
            "extract_claims",
            "assess_credibility",
            "cross_check",
            "read_memory",
            "save_evidence",
        ],
        notes_fa=(
            f"برنامه تحقیق محصول‌محور برای «{product}» از مبدأ {origin}"
            + (f" (HS={hs6})" if hs6 else " (HS نامشخص)")
            + " — بدون فهرست ثابت کشور"
        ),
    )
