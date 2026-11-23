"""Deterministic feasibility math — not LLM-invented."""

from __future__ import annotations

from app.schemas.contracts import CostItem, CostUpdate, Feasibility, ScenarioResult


def default_feasibility_template() -> Feasibility:
    return Feasibility(
        input_assumptions={
            "unit": "کیلوگرم",
            "quantity": None,
            "fx_rate_usd_irr": None,
            "target_sell_price_usd": None,
            "incoterm": "FOB",
        },
        cost_items=[
            CostItem(id="purchase", label_fa="قیمت خرید / تولید", amount=None, currency="USD", unit="کیلوگرم", required=True, note_fa="نامشخص / نیازمند تکمیل"),
            CostItem(id="packaging", label_fa="بسته‌بندی", amount=None, currency="USD", unit="کیلوگرم", required=True),
            CostItem(id="inland", label_fa="حمل داخلی", amount=None, currency="USD", unit="کیلوگرم", required=False),
            CostItem(id="intl_freight", label_fa="حمل بین‌المللی", amount=None, currency="USD", unit="کیلوگرم", required=True),
            CostItem(id="insurance", label_fa="بیمه", amount=None, currency="USD", unit="کیلوگرم", required=False),
            CostItem(id="duty", label_fa="تعرفه", amount=None, currency="USD", unit="کیلوگرم", required=True, note_fa="نامشخص / نیازمند تکمیل"),
            CostItem(id="fees", label_fa="کارمزدها", amount=None, currency="USD", unit="کیلوگرم", required=False),
        ],
        currency="USD",
        incoterm="FOB",
        scenario_results=[
            ScenarioResult(id="conservative", label_fa="محافظه‌کارانه", revenue=None, total_cost=None, margin=None, margin_pct=None, notes_fa=["ورودی ناقص"]),
            ScenarioResult(id="base", label_fa="میانه", revenue=None, total_cost=None, margin=None, margin_pct=None, notes_fa=["ورودی ناقص"]),
            ScenarioResult(id="optimistic", label_fa="خوش‌بینانه", revenue=None, total_cost=None, margin=None, margin_pct=None, notes_fa=["ورودی ناقص"]),
        ],
        missing_inputs=["قیمت خرید", "حمل بین‌المللی", "تعرفه", "قیمت فروش هدف", "تعداد/وزن"],
        caveats=[
            "محاسبه قطعی سمت سرور است؛ تا تکمیل ورودی‌ها نتیجه کامل نیست.",
            "ارائه‌دهنده تحقیق زنده هنوز وصل نیست — ارقام تجاری اختراع نمی‌شوند.",
        ],
        is_mock_sample=False,
    )


def recompute(feasibility: Feasibility, updates: list[CostUpdate] | None = None) -> Feasibility:
    items = list(feasibility.cost_items)
    if updates:
        by_id = {u.id: u.amount for u in updates}
        items = [
            c.model_copy(update={"amount": by_id[c.id]}) if c.id in by_id else c for c in items
        ]

    assumptions = dict(feasibility.input_assumptions)
    qty = float(assumptions.get("quantity") or 0) or 0.0
    sell = float(assumptions.get("target_sell_price_usd") or 0) or 0.0
    unit_cost = sum(float(c.amount or 0) for c in items)
    missing = [c.label_fa for c in items if c.required and c.amount is None]
    if not qty:
        missing.append("تعداد/وزن")
    if not sell:
        missing.append("قیمت فروش هدف")
    missing = list(dict.fromkeys(missing))

    if missing:
        scenarios = [
            s.model_copy(
                update={
                    "revenue": None,
                    "total_cost": None,
                    "margin": None,
                    "margin_pct": None,
                    "notes_fa": ["ورودی ناقص — محاسبه کامل ممکن نیست"],
                }
            )
            for s in feasibility.scenario_results
        ]
        return feasibility.model_copy(
            update={
                "cost_items": items,
                "missing_inputs": missing,
                "scenario_results": scenarios,
                "is_mock_sample": False,
            }
        )

    factors = {"conservative": 0.88, "base": 1.0, "optimistic": 1.12}
    cost_factors = {"conservative": 1.05, "base": 1.0, "optimistic": 0.95}
    scenarios = []
    for s in feasibility.scenario_results:
        revenue = round(qty * sell * factors[s.id])
        total_cost = round(qty * unit_cost * cost_factors[s.id])
        margin = revenue - total_cost
        margin_pct = round((margin / revenue) * 1000) / 10 if revenue else None
        scenarios.append(
            s.model_copy(
                update={
                    "revenue": revenue,
                    "total_cost": total_cost,
                    "margin": margin,
                    "margin_pct": margin_pct,
                    "notes_fa": ["محاسبه قطعی سمت سرور"],
                }
            )
        )

    return feasibility.model_copy(
        update={
            "cost_items": items,
            "missing_inputs": [],
            "scenario_results": scenarios,
            "is_mock_sample": False,
        }
    )
