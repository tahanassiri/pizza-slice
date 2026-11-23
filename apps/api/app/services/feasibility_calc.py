"""Deterministic feasibility math — not LLM-invented."""

from __future__ import annotations

from math import isfinite

from app.core.errors import AppError
from app.schemas.contracts import CostItem, CostUpdate, Feasibility, ScenarioResult


INCOTERM_NOTE = "اینکوترمز در گزارش ثبت می‌شود. فقط هزینه‌های سهم فروشنده را به ازای هر واحد وارد کنید و برای هزینهٔ نامربوط صفر بزنید."


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
            CostItem(id="inland", label_fa="حمل داخلی", amount=None, currency="USD", unit="کیلوگرم", required=True),
            CostItem(id="intl_freight", label_fa="حمل بین‌المللی", amount=None, currency="USD", unit="کیلوگرم", required=True),
            CostItem(id="insurance", label_fa="بیمه", amount=None, currency="USD", unit="کیلوگرم", required=True),
            CostItem(id="duty", label_fa="تعرفه", amount=None, currency="USD", unit="کیلوگرم", required=True, note_fa="نامشخص / نیازمند تکمیل"),
            CostItem(id="fees", label_fa="کارمزدها", amount=None, currency="USD", unit="کیلوگرم", required=True),
        ],
        currency="USD",
        incoterm="FOB",
        scenario_results=[
            ScenarioResult(id="conservative", label_fa="محافظه‌کارانه", revenue=None, total_cost=None, margin=None, margin_pct=None, notes_fa=["ورودی ناقص"]),
            ScenarioResult(id="base", label_fa="میانه", revenue=None, total_cost=None, margin=None, margin_pct=None, notes_fa=["ورودی ناقص"]),
            ScenarioResult(id="optimistic", label_fa="خوش‌بینانه", revenue=None, total_cost=None, margin=None, margin_pct=None, notes_fa=["ورودی ناقص"]),
        ],
        missing_inputs=[
            "قیمت خرید / تولید", "بسته‌بندی", "حمل داخلی", "حمل بین‌المللی",
            "بیمه", "تعرفه", "کارمزدها", "تعداد/وزن", "قیمت فروش هدف",
        ],
        caveats=[
            "محاسبه قطعی سمت سرور است؛ تا تکمیل ورودی‌ها نتیجه کامل نیست.",
            "ارائه‌دهنده تحقیق زنده هنوز وصل نیست — ارقام تجاری اختراع نمی‌شوند.",
            INCOTERM_NOTE,
        ],
        is_mock_sample=False,
    )


def _assumption_number(value, *, positive: bool = False) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) and number >= 0 and (not positive or number > 0) else None


def recompute(feasibility: Feasibility, updates: list[CostUpdate] | None = None) -> Feasibility:
    assumptions = dict(feasibility.input_assumptions)
    qty = _assumption_number(assumptions.get("quantity"))
    sell = _assumption_number(assumptions.get("target_sell_price_usd"))
    fx_rate = _assumption_number(assumptions.get("fx_rate_usd_irr"), positive=True)
    raw_incoterm = assumptions.get("incoterm", feasibility.incoterm)
    incoterm = raw_incoterm.upper() if isinstance(raw_incoterm, str) else None
    if incoterm is not None:
        assumptions["incoterm"] = incoterm

    by_id = {u.id: u for u in updates or []}
    items = []
    for item in feasibility.cost_items:
        raw_unit = assumptions.get("unit", item.unit)
        fields = {"unit": raw_unit if isinstance(raw_unit, str) else None, "required": True}
        if change := by_id.get(item.id):
            fields["amount"] = change.amount
            fields["currency"] = change.currency or item.currency
            if change.amount is not None:
                fields["note_fa"] = None
        items.append(item.model_copy(update=fields))

    missing = [c.label_fa for c in items if _assumption_number(c.amount) is None]
    if qty is None:
        missing.append("تعداد/وزن")
    if sell is None:
        missing.append("قیمت فروش هدف")
    if fx_rate is None and any(c.currency == "IRR" and c.amount for c in items):
        missing.append("نرخ تبدیل ریال به دلار")
    missing = list(dict.fromkeys(missing))
    common = {
        "input_assumptions": assumptions,
        "cost_items": items,
        "incoterm": incoterm,
        "caveats": list(dict.fromkeys([*feasibility.caveats, INCOTERM_NOTE])),
        "is_mock_sample": False,
    }

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
                **common,
                "missing_inputs": missing,
                "scenario_results": scenarios,
            }
        )

    unit_cost = sum(c.amount / fx_rate if c.currency == "IRR" and c.amount else c.amount for c in items)
    factors = {"conservative": 0.88, "base": 1.0, "optimistic": 1.12}
    cost_factors = {"conservative": 1.05, "base": 1.0, "optimistic": 0.95}
    scenarios = []
    for s in feasibility.scenario_results:
        revenue = round(qty * sell * factors[s.id], 0)
        total_cost = round(qty * unit_cost * cost_factors[s.id], 0)
        margin = revenue - total_cost
        margin_pct = round((margin / revenue) * 1000, 0) / 10 if revenue else None
        if not all(isfinite(value) for value in (revenue, total_cost, margin, margin_pct) if value is not None):
            raise AppError("INVALID_FEASIBILITY_INPUT", "عدد ورودی برای محاسبه بیش از حد بزرگ است.", 422)
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
            **common,
            "missing_inputs": [],
            "scenario_results": scenarios,
        }
    )
