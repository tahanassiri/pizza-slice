"""Deterministic market scoring — no fake confidence when data missing."""

from __future__ import annotations

from app.agents.policy import DEFAULT_WEIGHTS, SCORE_WEIGHT_BOUNDS
from app.agents.tool_contracts import MarketScoreCard, ScoreCriterion
from app.schemas.contracts import Market, MarketMetric, Source
from app.trade_data.wits import ISO3_NAME_FA, ISO3_TO_ISO2
from app.tools.extract import country_code, country_mentions


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
        year = rec.get("year") or reference_year
        product_specific = data_scope == "hs6"
        # Sector/total aggregates are context, not a product demand score.
        if product_specific:
            demand_value = min(1.0, share)
            demand_note = (
                f"سهم نسبی در دادهٔ محصول‌محور HS6 ({share*100:.1f}%) از {source_name}"
            )
            demand_confidence = "low"
        else:
            demand_value = None
            demand_note = (
                f"آمار {data_scope} از {source_name} برای رتبهٔ محصول استفاده نمی‌شود "
                f"(سهم گروهی {share*100:.1f}% فقط زمینه است)"
            )
            demand_confidence = "unknown"

        criteria = [
            _criterion(
                "demand",
                demand_value,
                confidence=demand_confidence,
                note=demand_note,
                refs=[source_name] if product_specific else [],
                date_scope=str(year) if year else None,
            ),
            _criterion(
                "access",
                None,
                confidence="unknown",
                note="دسترسی بازار بدون شاهد حمل/کانال نامعلوم است",
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

        # Trade rows do not crown markets. Recommendations require cited evidence ids.
        if not product_specific:
            total = None
        cards.append(
            MarketScoreCard(
                country_code=iso2,
                criteria=criteria,
                weights=w,
                total=total if product_specific else None,
                recommendation="watch",
                data_scope=data_scope if data_scope in {"hs6", "sector", "total", "qualitative"} else "sector",  # type: ignore[arg-type]
                rationale_fa=[
                    f"محصول: {product}",
                    f"منبع آمار: {source_name} ({data_scope})",
                    f"کیفیت: {quality_status}",
                    "رتبه‌بندی پیشنهادی از این ردیف ساخته نمی‌شود",
                ],
            )
        )
    return cards


_BANNED_SCORE_FILLERS = {0.35, 0.4, 0.5, 0.55}


def _proposal_evidence_ids(proposal: dict) -> list[str]:
    raw = proposal.get("evidence_ids")
    if isinstance(raw, list) and raw:
        return [str(item) for item in raw if str(item).strip()]
    return []


def _trade_supports_criterion(row: dict, criterion: str, country: str, origin: str | None) -> bool:
    trade = row.get("trade")
    if not trade:
        return True  # Prose remains bound to the model's cited destination and source.
    reporter, partner, flow = trade.get("reporter"), trade.get("partner"), trade.get("flow")
    if criterion == "competition":
        return flow == "export" and reporter == country
    if criterion not in {"demand", "access"}:
        return False
    if flow == "import":
        return reporter == country and (criterion == "demand" or bool(origin and partner == origin))
    return flow == "export" and partner == country and (criterion == "demand" or bool(origin and reporter == origin))


def validate_market_proposal(
    proposal: dict, *, product: str, origin: str, evidence_index: dict, visible: set[str],
) -> tuple[dict | None, str]:
    code = country_code(str(proposal.get("country_code") or ""))
    origin_code = country_code(origin)
    if not code or code == origin_code:
        return None, "invalid_destination"
    ids = list(dict.fromkeys(_proposal_evidence_ids(proposal)))
    if not ids:
        return None, "missing_claim_ids"
    rows = [evidence_index.get(ref) for ref in ids]
    if any(not row or not row.get("source_url") for row in rows):
        return None, "unknown_or_ambiguous_claim_id"
    if any(row["id"] not in visible for row in rows):
        return None, "claim_not_read"
    if any(str(row.get("product") or "").casefold() != product.casefold() for row in rows):
        return None, "product_mismatch"
    if any(row.get("country") and row["country"] != code for row in rows):
        return None, "country_mismatch"
    if not any(
        row.get("country") == code or code in country_mentions(str(row.get("statement") or ""))
        for row in rows
    ):
        return None, "no_destination_specific_evidence"
    if proposal.get("data_scope") in {"sector", "total"}:
        return None, "sector_or_total_is_not_product_evidence"
    family = proposal.get("data_scope") == "product_family"
    if proposal.get("recommendation") not in {"recommended", "risky", "watch"}:
        return None, "invalid_recommendation"
    if proposal["recommendation"] == "recommended" and not any(
        _trade_supports_criterion(row, "demand", code, origin_code) for row in rows
    ):
        return None, "no_destination_demand_or_purchase_evidence"
    by_id = {row["id"]: row for row in rows}
    ids = list(by_id)
    criteria: dict[str, list[str]] = {}
    raw_criteria = proposal.get("criteria")
    for item in raw_criteria if isinstance(raw_criteria, list) else []:
        key = item.get("criterion") if isinstance(item, dict) else None
        if not isinstance(key, str) or key not in SCORE_WEIGHT_BOUNDS:
            continue
        refs = item.get("evidence_ids")
        if isinstance(refs, list):
            refs = [ref for ref in ids if ref in refs and _trade_supports_criterion(by_id[ref], key, code, origin_code)]
            if refs:
                criteria[key] = refs
    if family and (proposal["recommendation"] != "watch" or not criteria.get("demand")):
        return None, "product_family_requires_watch_with_destination_demand_evidence"
    raw_risks = proposal.get("risks")
    return {
        "country_code": code,
        "recommendation": proposal["recommendation"],
        "data_scope": "product_family" if family else "qualitative",
        "evidence_ids": ids,
        "criteria": [{"criterion": key, "evidence_ids": refs} for key, refs in criteria.items()],
        "risks": [risk[:240] for risk in raw_risks[:3] if isinstance(risk, str)] if isinstance(raw_risks, list) else [],
    }, ""


def score_from_evidence_markets(
    proposals: list[dict],
    *,
    product: str,
    sources: list[Source] | None = None,
    evidence_index: dict[str, dict] | None = None,
) -> list[Market]:
    """LLM proposes countries. The backend keeps a proposal only when it cites stored evidence.

    Missing criteria stay unknown. Sector statistics cannot be relabeled as product demand.
    """

    index = evidence_index or {}
    product_l = (product or "").strip().lower()
    cards: list[MarketScoreCard] = []
    for proposal in proposals:
        code = str(proposal.get("country_code") or "").upper().strip()
        if len(code) != 2:
            continue
        evidence_ids = _proposal_evidence_ids(proposal)
        if not evidence_ids:
            continue
        cited: list[dict] = []
        rejected = False
        for evidence_id in evidence_ids:
            row = index.get(evidence_id)
            if not row or not str(row.get("source_url") or "").strip():
                rejected = True
                break
            row_product = str(row.get("product") or "").strip().lower()
            row_country = str(row.get("country") or "").upper().strip()
            if row_product and product_l and row_product != product_l and product_l not in row_product:
                rejected = True
                break
            if row_country and row_country != code:
                rejected = True
                break
            cited.append(row)
        if rejected or not cited:
            continue
        scopes = {str(row.get("data_scope") or "qualitative") for row in cited}
        sector_only = scopes <= {"sector", "total"}
        requested = str(proposal.get("recommendation") or "watch")
        if requested not in {"recommended", "risky", "watch"}:
            requested = "watch"
        requested_scope = str(proposal.get("data_scope") or "qualitative")
        if requested_scope not in {"hs6", "product_family", "sector", "total", "qualitative"}:
            requested_scope = "qualitative"
        if sector_only or requested_scope in {"sector", "total"}:
            # Do not publish a product winner from group statistics.
            continue
        if requested_scope == "product_family" and requested != "watch":
            continue
        if "sector" in scopes or "total" in scopes:
            requested_scope = "qualitative"
        statements = [str(row.get("statement") or "")[:240] for row in cited if row.get("statement")]
        criteria = [
            _criterion(
                "demand",
                None,
                confidence="unknown",
                note="شاهد اختصاصی برای معیار تقاضا ثبت نشده",
            ),
            _criterion("legal", None, confidence="unknown", note="نیازمند منبع رسمی روزآمد"),
            _criterion("logistics", None, confidence="unknown", note="نرخ حمل استعلام نشده"),
            _criterion("payment", None, confidence="unknown", note="مسیر پرداخت بررسی نشده"),
            _criterion("competition", None, confidence="unknown", note="رقابت تکمیل نشده"),
            _criterion("access", None, confidence="unknown", note="دسترسی بدون شاهد نامعلوم است"),
        ]
        for item in proposal.get("criteria") or []:
            key = item.get("criterion")
            refs = [ref for ref in (item.get("evidence_ids") or []) if ref in evidence_ids]
            if not refs:
                continue
            for criterion in criteria:
                if criterion.key == key:
                    criterion.evidence_refs = refs
                    criterion.note_fa = str(index[refs[0]].get("statement") or "")[:500]
                    criterion.date_scope = index[refs[0]].get("period")
                    break
        for criterion in criteria:
            if criterion.score_value in _BANNED_SCORE_FILLERS:
                criterion.score_value = None
                criterion.unknown = True
                criterion.confidence = "unknown"
        cards.append(
            MarketScoreCard(
                country_code=code,
                criteria=criteria,
                weights=clamp_weights(None),
                total=None,
                recommendation=requested,  # type: ignore[arg-type]
                data_scope=requested_scope,  # type: ignore[arg-type]
                rationale_fa=[
                    f"محصول: {product}",
                    *[f"شاهد {evidence_id}" for evidence_id in evidence_ids[:4]],
                    *statements[:3],
                    *[str(item) for item in (proposal.get("risks") or [])[:3]],
                    *(
                        ["عدم‌قطعیت: شاهد کیفی است و امتیاز عددی ساخته نشده."]
                        if requested == "watch"
                        else []
                    ),
                ],
            )
        )
    recommended = [card for card in cards if card.recommendation == "recommended"][:3]
    risky = [card for card in cards if card.recommendation == "risky"][:2]
    watch = [card for card in cards if card.recommendation == "watch"][:5]
    by_country = {
        str(proposal.get("country_code") or "").upper().strip(): {
            str((index.get(ref) or {}).get("source_url") or "") for ref in _proposal_evidence_ids(proposal)
        }
        for proposal in proposals
    }
    markets = cards_to_markets(recommended + risky + watch, source_name="cited-evidence")
    for market in markets:
        market.sources = [source for source in (sources or []) if source.url in by_country[market.country_code]]
    return markets


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
    watch_rank = 200
    for card in cards:
        if card.recommendation == "recommended":
            rec_rank += 1
            rank = rec_rank
        elif card.recommendation == "risky":
            risk_rank += 1
            rank = risk_rank
        elif card.recommendation == "watch" and card.data_scope in {"qualitative", "product_family"}:
            watch_rank += 1
            rank = watch_rank
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
        unknowns = [c.note_fa for c in card.criteria if c.unknown and not c.evidence_refs]
        risks = []
        if card.recommendation == "risky":
            risks.append("بازار پرریسک/هشدار — نباید با پیشنهاد اصلی اشتباه شود")
        if card.recommendation == "watch":
            risks.append("کیفی و نامطمئن — امتیاز عددی ساخته نشده است")
        if card.data_scope in {"sector", "total"}:
            risks.append("داده گروهی/کل است؛ تقاضای دقیق HS6 تأیید نشده")
        if card.data_scope == "product_family":
            risks.append("شاهد مربوط به خانوادهٔ محصول است؛ تقاضای محصول دقیق و دسترسی از مبدأ نامشخص‌اند.")

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
        if card.recommendation == "watch" or card.total is None:
            metrics.append(
                MarketMetric(
                    key="uncertainty",
                    label_fa="عدم‌قطعیت",
                    value="کیفی — امتیاز عددی ساخته نشده",
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
