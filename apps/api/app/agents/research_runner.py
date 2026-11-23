"""Bounded market research loop — tools + deterministic scoring."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy.orm import Session

from app.agents.market_scorer import cards_to_markets, score_from_trade_records
from app.agents.planner import build_research_plan
from app.agents.tool_contracts import ToolCall
from app.evidence.store import record_claim, record_evidence
from app.models.entities import MarketAssessment, Run
from app.schemas.contracts import Market, Source
from app.tools.executor import ToolExecutor

EmitFn = Callable[..., Awaitable[Any]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_market_research(
    db: Session,
    run: Run,
    executor: ToolExecutor,
    emit: EmitFn,
) -> dict[str, Any]:
    """Execute stages: classify → memory → plan → trade/search → score → persist."""

    # --- product classify ---
    await emit(
        db,
        run,
        phase="product_classify",
        status="running",
        message_fa="در حال شناسایی محصول و تعیین کد HS",
    )
    classify = executor.execute(
        ToolCall(
            tool="classify_product",
            args={"product": run.product, "hs_hint": run.guessed_hs_code},
        )
    )
    hs = classify.data.get("hs_code")
    hs_conf = classify.data.get("hs_confidence") or "unknown"
    if hs:
        run.guessed_hs_code = str(hs)
    run.hs_confidence = str(hs_conf)
    db.commit()
    await emit(
        db,
        run,
        phase="product_classify",
        status="completed",
        message_fa=(
            f"کد HS: {run.guessed_hs_code} (اطمینان {hs_conf})"
            if run.guessed_hs_code
            else f"HS قطعی ثبت نشد (اطمینان {hs_conf})"
        ),
        payload={
            "event_type": "product.ready",
            "guessed_hs_code": run.guessed_hs_code,
            "hs_confidence": hs_conf,
        },
    )

    # --- memory lookup ---
    await emit(
        db,
        run,
        phase="search",
        status="running",
        message_fa="بازیابی حافظه عمومی و طراحی برنامه تحقیق",
    )
    mem = executor.execute(
        ToolCall(
            tool="read_memory",
            args={
                "kind": "market_stats",
                "product": run.product,
                "hs6": run.guessed_hs_code,
                "origin": run.origin_country,
                "metric": "ranked_markets",
            },
        )
    )
    memory_status = (mem.data or {}).get("status") or "miss"
    cached_markets: list[Market] = []
    if memory_status in {"hit", "stale"} and mem.data.get("item"):
        try:
            payload = json.loads(mem.data["item"]["payload"])
            cached_markets = [Market.model_validate(m) for m in payload.get("markets") or []]
            if cached_markets:
                run.markets_json = json.dumps(
                    [m.model_dump() for m in cached_markets], ensure_ascii=False
                )
                db.commit()
                await emit(
                    db,
                    run,
                    phase="search",
                    status="partial",
                    message_fa=(
                        f"نتیجه حافظه ({memory_status}) نمایش داده شد"
                        + (
                            f" — تاریخ: {mem.data['item'].get('fetched_at')}"
                            if mem.data["item"].get("fetched_at")
                            else ""
                        )
                    ),
                    payload={
                        "event_type": "market.cache_hit",
                        "memory_status": memory_status,
                        "markets_found": len(cached_markets),
                        "fetched_at": mem.data["item"].get("fetched_at"),
                        "stale_after": mem.data["item"].get("stale_after"),
                    },
                )
        except Exception:
            cached_markets = []

    plan = build_research_plan(
        product=run.product, hs6=run.guessed_hs_code, origin=run.origin_country
    )
    await emit(
        db,
        run,
        phase="search",
        status="completed",
        message_fa=plan.notes_fa,
        payload={
            "event_type": "research.plan",
            "questions": plan.questions,
            "candidate_countries": plan.candidate_countries,
            "memory_status": memory_status,
        },
    )

    # If fresh cache hit, still optionally refresh in background path — for MVP refresh always
    # when stale or miss; on hit skip heavy trade if we already showed markets
    skip_heavy = memory_status == "hit" and bool(cached_markets)

    trade_data: dict[str, Any] = {}
    web_sources: list[Source] = []
    data_scope = "sector"

    if not skip_heavy:
        await emit(
            db,
            run,
            phase="trade_stats",
            status="running",
            message_fa="جمع‌آوری آمار رسمی/آزاد و شواهد تکمیلی",
        )
        trade = executor.execute(
            ToolCall(
                tool="get_trade_stats",
                args={
                    "product": run.product,
                    "origin": run.origin_country,
                    "hs6": run.guessed_hs_code,
                },
            )
        )
        trade_data = trade.data or {}
        data_scope = str(trade_data.get("data_scope") or "sector")

        # Attach provenance
        for p in trade.provenance or []:
            if p.get("url"):
                src = Source(
                    url=str(p["url"]),
                    title=str(p.get("publisher") or "trade"),
                    publisher=str(p.get("publisher") or "trade"),
                    fetched_at=str(p.get("fetched_at") or _now_iso()),
                    provider=str(trade_data.get("provider_id") or "trade"),
                    reliability_note=f"data_scope={data_scope}",
                )
                web_sources.append(src)
                record_evidence(db, run_id=run.id, source=src)

        await emit(
            db,
            run,
            phase="trade_stats",
            status="completed" if trade.ok else "partial",
            message_fa=trade.message_fa,
            source_refs=web_sources or None,
            error_code=None if trade.ok else trade.error_code,
            payload={
                "event_type": "market.evidence_ready",
                "quality_status": trade_data.get("quality_status"),
                "data_scope": data_scope,
                "cache_hit": trade_data.get("cache_hit"),
                "warnings": trade_data.get("warnings"),
            },
        )

        # regulations / logistics / context searches (bounded)
        for tool_name, label in (
            ("research_regulations", "مقررات"),
            ("research_logistics", "لجستیک"),
            ("search_web", "زمینه بازار"),
        ):
            args: dict[str, Any]
            if tool_name == "search_web":
                args = {
                    "query": f"{run.product} export market demand importers",
                    "max_results": 4,
                }
            elif tool_name == "research_regulations":
                args = {
                    "product": run.product,
                    "hs": run.guessed_hs_code,
                    "origin": run.origin_country,
                    "destination": plan.candidate_countries[0] if plan.candidate_countries else "AE",
                }
            else:
                args = {
                    "product": run.product,
                    "origin": run.origin_country,
                    "destination": plan.candidate_countries[0] if plan.candidate_countries else "AE",
                    "incoterm": "FOB",
                }
            res = executor.execute(ToolCall(tool=tool_name, args=args))
            for item in (res.data or {}).get("results") or []:
                if not item.get("url"):
                    continue
                src = Source(
                    url=item["url"],
                    title=item.get("title") or label,
                    publisher=item.get("publisher") or "web",
                    fetched_at=item.get("fetched_at") or _now_iso(),
                    provider="search",
                    reliability_note=f"qualitative:{label}",
                )
                web_sources.append(src)

        # Deduplicate sources
        seen_u: set[str] = set()
        deduped: list[Source] = []
        for s in web_sources:
            if s.url in seen_u:
                continue
            seen_u.add(s.url)
            deduped.append(s)
        web_sources = deduped

        await emit(
            db,
            run,
            phase="search",
            status="completed",
            message_fa=f"شواهد کیفی/وب: {len(web_sources)} منبع",
            source_refs=web_sources[:8] or None,
            payload={"event_type": "market.evidence_ready", "source_count": len(web_sources)},
        )

        records = list(trade_data.get("records") or [])
        cards = score_from_trade_records(
            records,
            data_scope=data_scope,
            source_name=str(trade_data.get("source_name") or "trade"),
            reference_year=trade_data.get("reference_year"),
            quality_status=str(trade_data.get("quality_status") or "unavailable"),
            product=run.product,
        )
        markets = cards_to_markets(
            cards,
            sources=web_sources[:5],
            reference_year=trade_data.get("reference_year"),
            source_name=str(trade_data.get("source_name") or "trade"),
        )

        # Emit incremental candidate events
        await emit(
            db,
            run,
            phase="market_compare",
            status="running",
            message_fa="رتبه‌بندی قطعی بازارها بر اساس شواهد موجود",
        )
        for m in markets:
            if m.metrics and any(
                x.key == "recommendation" and x.value == "recommended" for x in m.metrics
            ):
                await emit(
                    db,
                    run,
                    phase="market_compare",
                    status="partial",
                    message_fa=f"بازار پیشنهادی: {m.country_name_fa}",
                    payload={
                        "event_type": "market.candidate_ready",
                        "country_code": m.country_code,
                        "rank": m.rank,
                    },
                    source_refs=m.sources or None,
                )
            elif m.metrics and any(
                x.key == "recommendation" and x.value == "risky" for x in m.metrics
            ):
                await emit(
                    db,
                    run,
                    phase="market_compare",
                    status="partial",
                    message_fa=f"بازار پرریسک/هشدار: {m.country_name_fa}",
                    payload={
                        "event_type": "market.risky",
                        "country_code": m.country_code,
                        "rank": m.rank,
                    },
                )

        # Persist assessments + claims
        for card in cards:
            if card.recommendation not in {"recommended", "risky"}:
                continue
            db.add(
                MarketAssessment(
                    id=f"ma_{secrets.token_hex(8)}",
                    run_id=run.id,
                    country_code=card.country_code,
                    recommendation=card.recommendation,
                    score_json=card.model_dump_json(),
                    data_scope=card.data_scope,
                    payload_json=json.dumps(
                        {"product": run.product, "hs": run.guessed_hs_code},
                        ensure_ascii=False,
                    ),
                    created_at=datetime.now(timezone.utc),
                )
            )
            record_claim(
                db,
                run_id=run.id,
                statement=f"{card.recommendation}:{card.country_code} score={card.total}",
                data_kind="estimate" if card.data_scope != "hs6" else "fact",
                hs_scope=run.guessed_hs_code,
                country_scope=card.country_code,
                confidence="low" if card.data_scope != "hs6" else "medium",
            )
        db.commit()

        # Save public memory (no private fields)
        if markets:
            executor.execute(
                ToolCall(
                    tool="save_evidence",
                    args={
                        "kind": "market_stats",
                        "product": run.product,
                        "hs6": run.guessed_hs_code,
                        "origin": run.origin_country,
                        "metric": "ranked_markets",
                        "period": str(trade_data.get("reference_year") or ""),
                        "confidence": "low" if data_scope != "hs6" else "medium",
                        "published_period": str(trade_data.get("reference_year") or ""),
                        "payload": {
                            "markets": [m.model_dump() for m in markets],
                            "data_scope": data_scope,
                            "source_name": trade_data.get("source_name"),
                        },
                    },
                )
            )
    else:
        markets = cached_markets
        await emit(
            db,
            run,
            phase="trade_stats",
            status="completed",
            message_fa="استفاده از حافظه تازه — آمار سنگین تکرار نشد",
            payload={"event_type": "market.cache_reuse", "memory_status": memory_status},
        )
        await emit(
            db,
            run,
            phase="market_compare",
            status="running",
            message_fa="بازبینی رتبه‌بندی از حافظه",
        )

    run.markets_json = json.dumps([m.model_dump() for m in markets], ensure_ascii=False)
    db.commit()

    recommended = [
        m
        for m in markets
        if any(x.key == "recommendation" and x.value == "recommended" for x in m.metrics)
        or m.rank <= 3
    ]
    # Prefer explicit recommendation metric
    recommended = [
        m
        for m in markets
        if any(x.key == "recommendation" and x.value == "recommended" for x in m.metrics)
    ] or markets[:3]
    risky = [
        m
        for m in markets
        if any(x.key == "recommendation" and x.value == "risky" for x in m.metrics)
    ]

    status = "completed" if recommended else "partial"
    await emit(
        db,
        run,
        phase="market_compare",
        status=status,
        message_fa=(
            f"رتبه‌بندی: {len(recommended)} پیشنهاد، {len(risky)} پرریسک"
            if markets
            else "شواهد کافی برای رتبه‌بندی نبود"
        ),
        payload={
            "event_type": "market.ranked",
            "markets_found": len(markets),
            "recommended": [m.country_code for m in recommended],
            "risky": [m.country_code for m in risky],
            "data_scope": data_scope,
            "memory_status": memory_status,
        },
        error_code=None if markets else "INSUFFICIENT_EVIDENCE",
    )

    return {
        "markets": markets,
        "recommended": recommended,
        "risky": risky,
        "sources": web_sources,
        "data_scope": data_scope,
        "trade_meta": trade_data,
        "memory_status": memory_status,
        "plan": plan.model_dump(),
    }
