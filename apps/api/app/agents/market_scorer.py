"""Deterministic market scoring — no fake confidence when data missing."""

from __future__ import annotations

from app.agents.policy import DEFAULT_WEIGHTS, SCORE_WEIGHT_BOUNDS
from app.agents.tool_contracts import MarketScoreCard, ScoreCriterion
from app.schemas.contracts import Market, MarketMetric, Source
from app.trade_data.wits import ISO3_NAME_FA, ISO3_TO_ISO2


def clamp_weights(proposed: dict[str, float] | None) -> dict[str, float]:
    weights = dict(DEFAULT_WEIGHTS)
    if proposed:
        for k, v in proposed.items():
            if k not in SCORE_WEIGHT_BOUNDS:
                continue
            lo, hi = SCORE_WEIGHT_BOUNDS[k]
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            weights[k] = max(lo, min(hi, fv))
    # renormalize
    total = sum(weights.values()) or 1.0
    return {k: round(v / total, 4) for k, v in weights.items()}


def _criterion(
    key: str,
    value: float | None,
    *,
    confidence: str,
    note: str,
    refs: list[str] | None = None,
    date_scope: str | None = None,
) -> ScoreCriterion:
    unknown = value is None
    return ScoreCriterion(
        key=key,
        score_value=None if unknown else value,
        confidence="unknown" if unknown else confidence,  # type: ignore[arg-type]
        unknown=unknown,
        evidence_refs=refs or [],
        date_scope=date_scope,
        note_fa=note,
    )


def score_from_trade_records(
    records: list[dict],
    *,
    data_scope: str,
    source_name: str,
    reference_year: int | str | None,
    quality_status: str,
    product: str,
    weights: dict[str, float] | None = None,
    max_recommended: int = 3,
    max_risky: int = 2,
) -> list[MarketScoreCard]:
    """Score candidates from trade pool. Sector data → capped confidence & demand weight effect."""
    w = clamp_weights(weights)
    numeric = [r for r in records if r.get("value") is not None and float(r["value"]) > 0]
    if not numeric:
        return []
    pool_total = sum(float(r["value"]) for r in numeric)
    ranked = sorted(numeric, key=lambda r: float(r["value"]), reverse=True)

    cards: list[MarketScoreCard] = []
    for rec in ranked[: max_recommended + max_risky + 3]:
        iso3 = str(rec.get("reporter_iso3") or "")
        iso2 = ISO3_TO_ISO2.get(iso3, iso3[:2])
        value = float(rec["value"])
        share = value / pool_total if pool_total else 0.0
        # demand score from share (relative) — not absolute invented demand
        demand = min(1.0, share * 3.0)  # top ~33% share → 1.0
        year = rec.get("year") or reference_year

        # Without product-specific HS6, legal/payment/logistics unknown
        criteria = [
            _criterion(
                "demand",
                demand,
                confidence="medium" if data_scope == "hs6" else "low",
                note=(
                    f"سهم نسبی واردات در pool ({share*100:.1f}%) از {source_name} "
                    f"— دامنه داده: {data_scope}"
                ),
                refs=[source_name],
                date_scope=str(year) if year else None,
            ),
            _criterion(
                "access",
                0.55 if iso2 in {"AE", "TR", "IQ", "OM", "AZ", "AM", "GE", "PK"} else 0.4,
                confidence="low",
                note="نزدیکی تجاری تقریبی بر اساس تجربه منطقه — نیازمند شواهد لجستیک",
            ),
            _criterion(
                "logistics",
                None,
                confidence="unknown",
                note="نرخ حمل معتبر استعلام نشده",
            ),
            _criterion(
                "legal",
                None,
                confidence="unknown",
                note="مجوز/ممنوعیت با منبع رسمی روزآمد تأیید نشده",
            ),
            _criterion(
                "competition",
                None,
                confidence="unknown",
                note="تحلیل رقبا تکمیل نشده",
            ),
            _criterion(
                "payment",
                None,
                confidence="unknown",
                note="مسیر پرداخت/بیمه بررسی نشده",
            ),
        ]

        known = [c for c in criteria if not c.unknown and c.score_value is not None]
        if not known:
            total = None
        else:
            # Only score known criteria; scale by available weight mass (no fake zeros)
            avail_w = sum(w.get(c.key, 0) for c in known) or 1.0
            total = sum((w.get(c.key, 0) / avail_w) * float(c.score_value) for c in known)
            total = round(total, 4)

        # Cap recommendation quality when sector-only
        if data_scope in {"sector", "total"} and quality_status != "verified":
            # still allow recommended but mark low confidence via rationale
            pass

        cards.append(
            MarketScoreCard(
                country_code=iso2,
                criteria=criteria,
                weights=w,
                total=total,
                recommendation="watch",
                data_scope=data_scope if data_scope in {"hs6", "sector", "total", "qualitative"} else "sector",  # type: ignore[arg-type]
                rationale_fa=[
                    f"محصول: {product}",
                    f"منبع آمار: {source_name} ({data_scope})",
                    f"کیفیت: {quality_status}",
                ],
            )
        )

    # Assign recommended / risky from totals among those with some demand signal
    sortable = [c for c in cards if c.total is not None]
    sortable.sort(key=lambda c: float(c.total or 0), reverse=True)
    for i, c in enumerate(sortable):
        if i < max_recommended:
            c.recommendation = "recommended"
            c.rationale_fa.append("پیشنهاد اولیه بر اساس سیگنال تقاضا — نه حکم قطعی صادرات")
        elif i < max_recommended + max_risky:
            c.recommendation = "risky"
            c.rationale_fa.append(
                "ظاهراً جذاب از نظر حجم گروه کالایی اما شواهد محصول‌محور/قانونی ناکافی یا ریسک بالا"
            )
        else:
            c.recommendation = "watch"
    return sortable


def score_from_evidence_markets(
    proposals: list[dict],
    *,
    product: str,
    sources: list[Source] | None = None,
) -> list[Market]:
    """Build markets from LLM/agent proposals — only with evidence; never invent."""
    cards: list[MarketScoreCard] = []
    for p in proposals:
        code = str(p.get("country_code") or "").upper().strip()
        if len(code) != 2:
            continue
        evidence = [str(x) for x in (p.get("evidence") or []) if str(x).strip()]
        if not evidence:
            continue  # no evidence → skip (unknown stays unknown)
        rec = str(p.get("recommendation") or "watch")
        if rec not in {"recommended", "risky", "watch"}:
            rec = "watch"
        scope = str(p.get("data_scope") or "qualitative")
        if scope not in {"hs6", "sector", "total", "qualitative"}:
            scope = "qualitative"
        criteria = [
            _criterion(
                "demand",
                0.55 if rec == "recommended" else 0.35 if rec == "risky" else None,
                confidence="low",
                note=evidence[0][:240],
                refs=evidence[:2],
            ),
            _criterion("legal", None, confidence="unknown", note="نیازمند منبع رسمی روزآمد"),
            _criterion("logistics", None, confidence="unknown", note="نرخ حمل استعلام نشده"),
            _criterion("payment", None, confidence="unknown", note="مسیر پرداخت بررسی نشده"),
            _criterion("competition", None, confidence="unknown", note="رقابت تکمیل نشده"),
            _criterion("access", 0.4, confidence="low", note="برآورد کیفی دسترسی"),
        ]
        cards.append(
            MarketScoreCard(
                country_code=code,
                criteria=criteria,
                weights=clamp_weights(None),
                total=0.5 if rec == "recommended" else 0.35 if rec == "risky" else None,
                recommendation=rec,  # type: ignore[arg-type]
                data_scope=scope,  # type: ignore[arg-type]
                rationale_fa=[f"محصول: {product}", *evidence[:4], *(p.get("risks") or [])],
            )
        )
    # Cap counts
    recs = [c for c in cards if c.recommendation == "recommended"][:3]
    risks = [c for c in cards if c.recommendation == "risky"][:2]
    ordered = recs + risks
    return cards_to_markets(ordered, sources=sources, source_name="agentic-web")


def cards_to_markets(
    cards: list[MarketScoreCard],
    *,
    sources: list[Source] | None = None,
    reference_year: int | str | None = None,
    source_name: str = "trade",
) -> list[Market]:

    markets: list[Market] = []
    sources = sources or []
    rec_rank = 0
    risk_rank = 100
    for card in cards:
        if card.recommendation == "recommended":
            rec_rank += 1
            rank = rec_rank
        elif card.recommendation == "risky":
            risk_rank += 1
            rank = risk_rank
        else:
            continue

        name_fa = next(
            (ISO3_NAME_FA[k] for k, v in ISO3_TO_ISO2.items() if v == card.country_code),
            card.country_code,
        )
        # reverse map iso2→name via ISO3
        for iso3, iso2 in ISO3_TO_ISO2.items():
            if iso2 == card.country_code:
                name_fa = ISO3_NAME_FA.get(iso3, card.country_code)
                break

        conf = "low"
        if card.data_scope == "hs6" and card.total is not None:
            conf = "medium"
        if any(c.unknown for c in card.criteria):
            conf = "low" if conf != "unknown" else "unknown"

        demand = next((c for c in card.criteria if c.key == "demand"), None)
        evidence = list(card.rationale_fa)
        if demand and demand.note_fa:
            evidence.insert(0, demand.note_fa)
        unknowns = [c.note_fa for c in card.criteria if c.unknown]
        risks = []
        if card.recommendation == "risky":
            risks.append("بازار پرریسک/هشدار — نباید با پیشنهاد اصلی اشتباه شود")
        if card.data_scope in {"sector", "total"}:
            risks.append("داده گروهی/کل است؛ تقاضای دقیق HS6 تأیید نشده")

        metrics = [
            MarketMetric(
                key="score_total",
                label_fa="امتیاز نسبی (معیارهای معلوم)",
                value=f"{card.total:.3f}" if card.total is not None else "نامشخص",
                estimated=card.data_scope != "hs6",
            ),
            MarketMetric(
                key="data_scope",
                label_fa="دامنه داده",
                value=card.data_scope,
            ),
            MarketMetric(
                key="recommendation",
                label_fa="وضعیت پیشنهاد",
                value=card.recommendation,
            ),
            MarketMetric(
                key="source",
                label_fa="منبع",
                value=source_name,
            ),
        ]
        if reference_year:
            metrics.append(
                MarketMetric(
                    key="reference_year",
                    label_fa="سال مرجع",
                    value=str(reference_year),
                )
            )
        metrics.append(
            MarketMetric(
                key="data_quality",
                label_fa="کیفیت داده",
                value="partial" if card.data_scope != "hs6" else "verified",
            )
        )

        markets.append(
            Market(
                country_code=card.country_code,
                country_name_fa=name_fa,
                rank=rank,
                evidence=evidence[:6],
                opportunities=[
                    "سیگنال واردات در پوشش داده‌شده؛ کانال توزیع و تعرفه را جدا بررسی کنید"
                ]
                if card.recommendation == "recommended"
                else [],
                risks=risks,
                metrics=metrics,
                confidence=conf,  # type: ignore[arg-type]
                unknowns=unknowns[:6],
                sources=sources[:5],
            )
        )
    # sort: recommended by rank, then risky
    markets.sort(key=lambda m: m.rank)
    return markets
