"""Real iterative research loop: plan → tool → extract → verify → gaps → next action."""

from __future__ import annotations

import json
import time
from typing import Any, Awaitable, Callable

from sqlalchemy.orm import Session

from app.agents.llm_decide import AgentAction, decide_research_action
from app.agents.market_scorer import cards_to_markets, score_from_evidence_markets
from app.agents.tool_contracts import ToolCall
from app.evidence.store import record_claim
from app.models.entities import Run
from app.schemas.contracts import Market, Source
from app.tools.budget import BudgetExceeded, ensure_run_budget
from app.tools.executor import ToolExecutor

EmitFn = Callable[..., Awaitable[Any]]


def _budget_left(executor: ToolExecutor) -> dict[str, int]:
    b = executor.budget
    return {
        "model": max(0, b.max_model_calls - b.model_calls_used),
        "search": max(0, b.max_search_queries - b.search_queries_used),
        "pages": max(0, b.max_pages - b.pages_used),
    }


def _summarize_evidence(state: dict[str, Any]) -> str:
    parts = []
    for item in state.get("tool_trace") or []:
        parts.append(f"- {item.get('tool')}: {item.get('message_fa')} ok={item.get('ok')}")
    for c in (state.get("claims") or [])[:12]:
        parts.append(f"CLAIM: {c.get('statement', '')[:160]} [{c.get('source_url')}]")
    for u in state.get("urls") or []:
        parts.append(f"URL: {u}")
    return "\n".join(parts)[:6000]


async def run_decision_loop(
    db: Session,
    run: Run,
    executor: ToolExecutor,
    emit: EmitFn,
    *,
    max_iterations: int | None = None,
) -> dict[str, Any]:
    """LLM-driven research. Budgets checked before each tool call. Honest partial on stop."""

    ensure_run_budget(db, run.id)
    b = executor.budget
    max_iter = max_iterations or min(12, max(4, b.max_model_calls))
    wall = max(30, int(b.max_wall_seconds or 180))
    started = time.monotonic()

    state: dict[str, Any] = {
        "tool_trace": [],
        "claims": [],
        "urls": [],
        "conflicts": [],
        "unknowns": [],
        "open_questions": [
            f"کدام بازارها برای «{run.product}» از مبدأ {run.origin_country} با شواهد قابل دفاع‌اند؟",
            "محدودیت قانونی/استاندارد/پرداخت/حمل چیست؟",
            "رقابت و دغدغه واردکننده/صادرکننده چیست؟",
        ],
        "strategy": "broad_web_discovery",
    }

    # --- product classify (tool, budgeted) ---
    await emit(
        db,
        run,
        phase="product_classify",
        status="running",
        message_fa="شناسایی محصول و ابهام HS",
    )
    classify = executor.execute(
        ToolCall(tool="classify_product", args={"product": run.product, "hs_hint": run.guessed_hs_code})
    )
    if classify.data.get("hs_code"):
        run.guessed_hs_code = str(classify.data["hs_code"])
    run.hs_confidence = str(classify.data.get("hs_confidence") or "unknown")
    db.commit()
    await emit(
        db,
        run,
        phase="product_classify",
        status="completed",
        message_fa=(
            f"HS: {run.guessed_hs_code or 'نامشخص'} (اطمینان {run.hs_confidence})"
        ),
        payload={
            "event_type": "product.ready",
            "guessed_hs_code": run.guessed_hs_code,
            "hs_confidence": run.hs_confidence,
        },
    )

    # --- memory (period-stable key: empty period; year lives in published_period) ---
    await emit(
        db,
        run,
        phase="search",
        status="running",
        message_fa="بازیابی حافظه و شروع حلقه تصمیم ایجنت",
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
                "period": "",  # stable key — do not mismatch year on lookup
            },
        )
    )
    memory_status = (mem.data or {}).get("status") or "miss"
    cached_markets: list[Market] = []
    if memory_status in {"hit", "stale"} and mem.data.get("item"):
        try:
            payload = json.loads(mem.data["item"]["payload"])
            cached_markets = [Market.model_validate(m) for m in payload.get("markets") or []]
            await emit(
                db,
                run,
                phase="search",
                status="partial",
                message_fa=f"حافظه عمومی: {memory_status}"
                + (
                    f" (fetched {mem.data['item'].get('fetched_at')})"
                    if mem.data["item"].get("fetched_at")
                    else ""
                ),
                payload={
                    "event_type": "market.cache_hit",
                    "memory_status": memory_status,
                    "stale_after": mem.data["item"].get("stale_after"),
                    "published_period": mem.data["item"].get("published_period"),
                    "markets_found": len(cached_markets),
                },
            )
            if memory_status == "hit" and cached_markets:
                # Serve immediately; still allow one refresh iteration if budget remains
                state["cached_hit"] = True
        except Exception:
            cached_markets = []

    await emit(
        db,
        run,
        phase="search",
        status="running",
        message_fa="حلقه تحقیق ایجنت‌محور (تصمیم مدل / راهبرد پویا)",
        payload={"event_type": "research.loop_start", "max_iterations": max_iter},
    )

    final_action: AgentAction | None = None
    for iteration in range(max_iter):
        if time.monotonic() - started > wall:
            final_action = AgentAction(
                action="conclude",
                stop_reason="wall_time",
                rationale_fa="سقف زمان تحقیق تمام شد",
                unknowns=list(state["unknowns"]) or ["زمان ناکافی برای تکمیل شواهد"],
            )
            break

        left = _budget_left(executor)
        if left["search"] <= 0 and left["pages"] <= 0 and left["model"] <= 0:
            final_action = AgentAction(
                action="conclude",
                stop_reason="budget_exhausted",
                rationale_fa="بودجه ابزار/مدل تمام شد",
                unknowns=["ادامه تحقیق نیازمند افزایش بودجه ادمین"],
            )
            break

        # Fresh hit: optionally skip heavy refresh
        if state.get("cached_hit") and iteration == 0 and memory_status == "hit":
            action = AgentAction(
                action="conclude",
                rationale_fa="استفاده از حافظه تازه با برچسب تاریخ",
                stop_reason="memory_hit",
                market_proposals=[
                    {
                        "country_code": m.country_code,
                        "recommendation": next(
                            (x.value for x in m.metrics if x.key == "recommendation"),
                            "recommended" if m.rank <= 3 else "watch",
                        ),
                        "evidence": m.evidence,
                        "data_scope": next(
                            (x.value for x in m.metrics if x.key == "data_scope"), "qualitative"
                        ),
                        "risks": m.risks,
                    }
                    for m in cached_markets
                ],
            )
        else:
            action = decide_research_action(
                executor.llm,
                product=run.product,
                origin=run.origin_country,
                hs6=run.guessed_hs_code,
                iteration=iteration,
                max_iterations=max_iter,
                evidence_summary=_summarize_evidence(state),
                open_questions=state["open_questions"],
                budget_left=left,
            )

        await emit(
            db,
            run,
            phase="search",
            status="running",
            message_fa=action.rationale_fa or f"اقدام ایجنت: {action.action}",
            payload={
                "event_type": "research.decision",
                "iteration": iteration,
                "action": action.action,
                "tool": action.tool,
                # never emit raw chain-of-thought beyond short rationale
            },
        )

        if action.action in {"conclude", "ask_user"}:
            final_action = action
            break

        if action.action == "change_strategy":
            state["strategy"] = str(action.args.get("strategy") or "alternate_sources")
            state["open_questions"].append("راهبرد تغییر کرد — منابع جایگزین لازم است")
            continue

        if action.action == "verify_conflict":
            cross = executor.execute(
                ToolCall(tool="cross_check", args={"claims": state["claims"]})
            )
            state["conflicts"].extend((cross.data or {}).get("conflicts") or [])
            state["tool_trace"].append(
                {"tool": "cross_check", "ok": cross.ok, "message_fa": cross.message_fa}
            )
            continue

        if action.action != "call_tool" or not action.tool:
            final_action = AgentAction(
                action="conclude",
                stop_reason="invalid_action",
                rationale_fa="اقدام نامعتبر از تصمیم‌یار",
                unknowns=["تصمیم مدل قابل اجرا نبود"],
            )
            break

        # Budget gate BEFORE call (also enforced inside executor)
        need = "search" if action.tool in {"search_web", "research_regulations", "research_logistics"} else (
            "page" if action.tool in {"fetch_page", "verify_company"} else "model"
        )
        if need == "search" and left["search"] <= 0:
            state["unknowns"].append("سقف جست‌وجو تمام شد")
            continue
        if need == "page" and left["pages"] <= 0:
            state["unknowns"].append("سقف خواندن صفحه تمام شد")
            continue

        try:
            result = executor.execute(ToolCall(tool=action.tool, args=action.args or {}))
        except BudgetExceeded as exc:
            final_action = AgentAction(
                action="conclude",
                stop_reason="budget_exceeded",
                rationale_fa=exc.message_fa,
            )
            break

        state["tool_trace"].append(
            {
                "tool": action.tool,
                "ok": result.ok,
                "message_fa": result.message_fa,
                "error_code": result.error_code,
            }
        )

        # Collect URLs / claims
        for item in (result.data or {}).get("results") or []:
            if item.get("url"):
                state["urls"].append(item["url"])
        if action.tool == "fetch_page" and result.ok:
            url = str((result.data or {}).get("url") or action.args.get("url") or "")
            text = str((result.data or {}).get("text") or "")
            if url:
                state["urls"].append(url)
                cred = executor.execute(
                    ToolCall(
                        tool="assess_credibility",
                        args={"url": url, "title": "", "publisher": ""},
                    )
                )
                state["tool_trace"].append(
                    {"tool": "assess_credibility", "ok": cred.ok, "message_fa": cred.message_fa}
                )
                extracted = executor.execute(
                    ToolCall(
                        tool="extract_claims",
                        args={"text": text, "url": url, "product": run.product},
                    )
                )
                for cl in (extracted.data or {}).get("claims") or []:
                    state["claims"].append(cl)
                    record_claim(
                        db,
                        run_id=run.id,
                        statement=str(cl.get("statement") or "")[:2000],
                        data_kind="estimate",
                        hs_scope=run.guessed_hs_code,
                        confidence="low",
                    )
                await emit(
                    db,
                    run,
                    phase="trade_stats",
                    status="partial",
                    message_fa=f"شواهد صفحه استخراج شد ({len((extracted.data or {}).get('claims') or [])} ادعا)",
                    payload={"event_type": "market.evidence_ready", "url": url},
                    source_refs=[
                        Source(
                            url=url,
                            title=url,
                            publisher="web",
                            fetched_at=str((result.data or {}).get("fetched_at") or ""),
                            provider="fetch_page",
                            reliability_note=str((cred.data or {}).get("level") or "low"),
                        )
                    ]
                    if url
                    else None,
                )
        elif action.tool == "search_web" and result.ok:
            await emit(
                db,
                run,
                phase="search",
                status="partial",
                message_fa=result.message_fa,
                payload={
                    "event_type": "market.evidence_ready",
                    "result_count": len((result.data or {}).get("results") or []),
                },
            )
        elif not result.ok and result.error_code in {
            "WEB_SEARCH_BLOCKED",
            "PROVIDER_UNAVAILABLE",
            "SSRF_BLOCKED",
        }:
            state["unknowns"].append(result.message_fa)

        # Persist checkpoint for durable resume
        from app.jobs.durable import latest_task_for_run
        from app.models.entities import ResearchTask

        task = latest_task_for_run(db, run.id)
        if task:
            task.checkpoint_json = json.dumps(
                {"iteration": iteration, "state_urls": state["urls"][:20], "claims": len(state["claims"])},
                ensure_ascii=False,
            )
            db.commit()

    if final_action is None:
        final_action = AgentAction(
            action="conclude",
            stop_reason="max_iterations",
            rationale_fa="سقف تکرار حلقه تحقیق تمام شد",
            unknowns=["شواهد ناکافی پس از سقف تکرار"],
        )

    # Build markets from proposals if any; else empty → honest partial
    proposals = list(final_action.market_proposals or [])
    markets: list[Market] = []
    if proposals:
        markets = score_from_evidence_markets(
            proposals,
            product=run.product,
            sources=[
                Source(
                    url=u,
                    title=u,
                    publisher="web",
                    fetched_at="",
                    provider="free_web",
                    reliability_note="web evidence",
                )
                for u in state["urls"][:5]
            ],
        )
    elif cached_markets and final_action.stop_reason == "memory_hit":
        markets = cached_markets

    # Persist memory with stable period key
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
                    "period": "",  # MUST match lookup
                    "published_period": "",
                    "confidence": "low",
                    "payload": {
                        "markets": [m.model_dump() for m in markets],
                        "data_scope": "qualitative",
                        "stop_reason": final_action.stop_reason,
                    },
                },
            )
        )

    recommended = [
        m
        for m in markets
        if any(x.key == "recommendation" and x.value == "recommended" for x in m.metrics)
    ]
    risky = [
        m
        for m in markets
        if any(x.key == "recommendation" and x.value == "risky" for x in m.metrics)
    ]

    run.markets_json = json.dumps([m.model_dump() for m in markets], ensure_ascii=False)
    db.commit()

    status = "completed" if recommended else "partial"
    await emit(
        db,
        run,
        phase="market_compare",
        status=status,
        message_fa=(
            f"پایان حلقه: {len(recommended)} پیشنهاد، {len(risky)} پرریسک — {final_action.rationale_fa}"
            if markets
            else f"نتیجه ناقص: {final_action.rationale_fa}"
        ),
        payload={
            "event_type": "market.ranked" if markets else "task.partial",
            "stop_reason": final_action.stop_reason,
            "recommended": [m.country_code for m in recommended],
            "risky": [m.country_code for m in risky],
            "tool_trace": state["tool_trace"],
            "memory_status": memory_status,
            "conflicts": state["conflicts"] + list(final_action.conflicts or []),
            "unknowns": list(dict.fromkeys([*state["unknowns"], *final_action.unknowns])),
        },
        error_code=None if markets else "INSUFFICIENT_EVIDENCE",
    )

    sources = [
        Source(
            url=u,
            title=u,
            publisher="web",
            fetched_at="",
            provider="free_web",
            reliability_note="discovered during agent loop",
        )
        for u in list(dict.fromkeys(state["urls"]))[:12]
    ]

    return {
        "markets": markets,
        "recommended": recommended,
        "risky": risky,
        "sources": sources,
        "data_scope": "qualitative",
        "trade_meta": {
            "quality_status": "partial" if markets else "unavailable",
            "source_name": "Agentic free-web research",
            "warnings": state["conflicts"] + state["unknowns"],
        },
        "memory_status": memory_status,
        "plan": {
            "questions": state["open_questions"],
            "notes_fa": final_action.rationale_fa,
            "tools_needed": sorted({t["tool"] for t in state["tool_trace"] if t.get("tool")}),
        },
        "tool_trace": state["tool_trace"],
        "stop_reason": final_action.stop_reason,
        "unknowns": list(dict.fromkeys([*state["unknowns"], *final_action.unknowns])),
        "conflicts": state["conflicts"] + list(final_action.conflicts or []),
    }
