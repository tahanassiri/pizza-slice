"""Research loop. The active LLM decides, or the run is blocked. No heuristic substitute."""

from __future__ import annotations

import json
import time
from typing import Any, Awaitable, Callable

from sqlalchemy.orm import Session

from app.agents.llm_decide import (
    render_decision_prompt,
    AgentAction,
    blocked_action,
    build_decision_context,
    explain_decision,
    llm_is_research_decision_maker,
    parse_model_decision,
    pending_steps,
)
from app.agents.loop_safety import action_signature, operational_stop
from app.agents.research_phase import buyer_research_blocked, premature_market_stop
from app.agents.market_scorer import score_from_evidence_markets
from app.agents.tool_contracts import ToolCall
from app.evidence.store import evidence_index_for_run, record_claim
from app.jobs.durable import renew_lease, write_checkpoint
from app.models.entities import Run
from app.schemas.contracts import Market, Source
from app.providers.keyed import ModelCallError
from app.tools.budget import BudgetExceeded, ensure_run_budget, guarded_model_call
from app.tools.executor import ToolExecutor

_MODEL_CODE = {
    "Billing problem": "MODEL_BILLING",
    "Rate-limited": "MODEL_RATE_LIMITED",
    "Unavailable": "MODEL_UNAVAILABLE",
    "Failed": "MODEL_FAILED",
}

EmitFn = Callable[..., Awaitable[Any]]


def _remember_model_status(db: Session, status: str) -> None:
    from app.services.admin_service import _write_model_verification, get_selected_model

    _write_model_verification(db, get_selected_model(db), status)


def _budget_left(executor: ToolExecutor) -> dict[str, int]:
    """Counts are not a stop. The prompt must not tell the model a cap is gone."""

    _ = executor.budget
    return {"model": 1000, "search": 1000, "pages": 1000}


def _touch(db: Session, task_id: str | None, owner: str | None, checkpoint: dict[str, Any]) -> bool:
    if not task_id or not owner:
        return True
    if not renew_lease(db, task_id, owner):
        return False
    write_checkpoint(db, task_id, checkpoint)
    return True


async def run_decision_loop(
    db: Session,
    run: Run,
    executor: ToolExecutor,
    emit: EmitFn,
    *,
    max_iterations: int | None = None,
    checkpoint: dict[str, Any] | None = None,
    task_id: str | None = None,
    lease_owner: str | None = None,
) -> dict[str, Any]:
    ensure_run_budget(db, run.id)
    del max_iterations
    checkpoint = dict(checkpoint or {})
    checkpoint.setdefault("version", 2)
    completed = list(checkpoint.get("completed_steps") or [])
    state: dict[str, Any] = dict(checkpoint.get("state") or {})
    state.setdefault("tool_trace", [])
    state.setdefault("claims", [])
    state.setdefault("urls", [])
    state.setdefault("conflicts", [])
    state.setdefault("unknowns", [])
    state.setdefault(
        "open_questions",
        [
            f"کدام بازارها برای «{run.product}» از مبدأ {run.origin_country} با شواهد قابل دفاع‌اند؟",
            "محدودیت قانونی/استاندارد/پرداخت/حمل چیست؟",
            "رقابت و دغدغه واردکننده/صادرکننده چیست؟",
        ],
    )
    tools_invoked: list[str] = list(checkpoint.get("tools_invoked") or [])
    iteration = int(checkpoint.get("decision_iteration") or 0)

    def persist() -> bool:
        checkpoint["version"] = 2
        checkpoint["decision_iteration"] = iteration
        checkpoint["completed_steps"] = completed
        if state.get("memory_status"):
            checkpoint["memory_status"] = state["memory_status"]
        checkpoint["state"] = {
            "tool_trace": state["tool_trace"][-30:],
            "claims": state["claims"][-20:],
            "urls": state["urls"][:20],
            "conflicts": state["conflicts"][:12],
            "unknowns": state["unknowns"][:12],
            "open_questions": state["open_questions"][:8],
        }
        checkpoint["tools_invoked"] = tools_invoked[-40:]
        return _touch(db, task_id, lease_owner, checkpoint)

    def remember(step: str) -> bool:
        if step not in completed:
            completed.append(step)
        return persist()

    todo = pending_steps({"completed_steps": completed})

    if "classify" in todo:
        await emit(
            db,
            run,
            phase="product_classify",
            status="running",
            message_fa="شناسایی محصول و ابهام HS",
            event_id=f"evt_{run.id}_classify_running",
        )
        classify = executor.execute(
            ToolCall(tool="classify_product", args={"product": run.product, "hs_hint": run.guessed_hs_code})
        )
        if not classify.ok and str(classify.error_code or "").startswith("MODEL_"):
            final_action = blocked_action(str(classify.error_code), classify.message_fa)
            await emit(
                db,
                run,
                phase="product_classify",
                status="partial",
                message_fa=classify.message_fa,
                error_code=classify.error_code,
                event_id=f"evt_{run.id}_classify_failed",
            )
            return await _finish(
                db, run, executor, emit, state, final_action, [], "miss", tools_invoked
            )
        tools_invoked.append("classify_product")
        if classify.data.get("hs_code"):
            run.guessed_hs_code = str(classify.data["hs_code"])
        run.hs_confidence = str(classify.data.get("hs_confidence") or "unknown")
        db.commit()
        await emit(
            db,
            run,
            phase="product_classify",
            status="completed",
            message_fa=f"HS: {run.guessed_hs_code or 'نامشخص'} (اطمینان {run.hs_confidence})",
            payload={
                "event_type": "product.ready",
                "guessed_hs_code": run.guessed_hs_code,
                "hs_confidence": run.hs_confidence,
            },
            event_id=f"evt_{run.id}_classify_done",
        )
        if not remember("classify"):
            return _lease_lost(state, run)
    else:
        tools_invoked.append("skipped:classify")

    memory_status = "miss"
    state["memory_status"] = memory_status
    cached_markets: list[Market] = []
    if "memory" in todo:
        await emit(
            db,
            run,
            phase="search",
            status="running",
            message_fa="بازیابی حافظه",
            event_id=f"evt_{run.id}_memory_running",
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
                    "period": "",
                },
            )
        )
        tools_invoked.append("read_memory")
        memory_status = (mem.data or {}).get("status") or "miss"
        state["memory_status"] = memory_status
        if memory_status in {"hit", "stale"} and mem.data.get("item"):
            try:
                payload = json.loads(mem.data["item"]["payload"])
                cached_markets = [Market.model_validate(item) for item in payload.get("markets") or []]
            except Exception:
                cached_markets = []
            await emit(
                db,
                run,
                phase="search",
                status="partial",
                message_fa=f"حافظه عمومی: {memory_status}",
                payload={
                    "event_type": "market.cache_hit",
                    "memory_status": memory_status,
                    "stale_after": mem.data["item"].get("stale_after"),
                    "published_period": mem.data["item"].get("published_period"),
                    "markets_found": len(cached_markets),
                },
                event_id=f"evt_{run.id}_memory_{memory_status}",
            )
        else:
            await emit(
                db,
                run,
                phase="search",
                status="completed",
                message_fa="حافظه عمومی برای این محصول پیدا نشد",
                payload={"event_type": "market.cache_miss", "memory_status": memory_status},
                event_id=f"evt_{run.id}_memory_miss",
            )
        if not remember("memory"):
            return _lease_lost(state, run)
    else:
        tools_invoked.append("skipped:memory")
        memory_status = str(checkpoint.get("memory_status") or "miss")
        state["memory_status"] = memory_status

    if memory_status == "hit" and cached_markets:
        final_action = AgentAction(
            action="conclude",
            rationale_fa="حافظه تازه با برچسب تاریخ نمایش داده شد. این تصمیم مدل نیست.",
            stop_reason="memory_hit",
            decision_source="blocked",
            market_proposals=[],
        )
        markets = cached_markets
        remember("decide")
        return await _finish(
            db,
            run,
            executor,
            emit,
            state,
            final_action,
            markets,
            memory_status,
            tools_invoked,
        )

    if not llm_is_research_decision_maker(executor.llm):
        if getattr(executor.llm, "id", "") == "stub_llm":
            reason = "حالت آزمایشی stub است و مدل زنده فراخوانی نشد. تصمیم اکتشافی اجرا نشد."
        else:
            reason = (
                "مدل انتخاب‌شده ادمین کلید قابل استفاده یا وضعیت اتصال معتبر ندارد. "
                "مدل دیگری جایگزین نشد و تصمیم اکتشافی اجرا نشد."
            )
        final_action = blocked_action("LLM_UNAVAILABLE", reason)
        await emit(
            db,
            run,
            phase="search",
            status="partial",
            message_fa=final_action.rationale_fa,
            payload={
                "event_type": "research.blocked",
                "recoverable": True,
                "blocked_code": "LLM_UNAVAILABLE",
                "decision_source": "blocked",
            },
            error_code="LLM_UNAVAILABLE",
            event_id=f"evt_{run.id}_research_blocked",
        )
        remember("decide")
        return await _finish(
            db,
            run,
            executor,
            emit,
            state,
            final_action,
            [],
            memory_status,
            tools_invoked,
        )

    await emit(
        db,
        run,
        phase="search",
        status="running",
        message_fa="حلقه تحقیق — تصمیم با مدل فعال",
        payload={"event_type": "research.loop_start", "decision_source": "llm"},
        event_id=f"evt_{run.id}_loop_start",
    )

    final_action: AgentAction | None = None
    evidence_index = evidence_index_for_run(db, run.id)
    from app.services.admin_service import read_safety

    safety = read_safety(db)
    tokens_before = int(checkpoint.get("tokens_used") or 0)
    session_started = time.monotonic()
    invalid_streak = int(checkpoint.get("invalid_streak") or 0)
    repeated = int(checkpoint.get("repeated_actions") or 0)
    last_signature = str(checkpoint.get("last_signature") or "")

    def _elapsed() -> float:
        return float(checkpoint.get("active_seconds") or 0) + (time.monotonic() - session_started)

    def _tokens() -> int:
        return tokens_before + int(getattr(executor.llm, "tokens_used", 0) or 0)

    def _cancelled() -> bool:
        db.refresh(run)
        return run.status == "cancelled"

    def _remember_safety() -> None:
        checkpoint["invalid_streak"] = invalid_streak
        checkpoint["repeated_actions"] = repeated
        checkpoint["last_signature"] = last_signature
        checkpoint["active_seconds"] = _elapsed()
        checkpoint["tokens_used"] = _tokens()
        state["tokens_used"] = _tokens()
        state["estimated_cost_usd"] = float(getattr(executor.llm, "cost_usd", 0) or 0)
        state["output_method"] = str(getattr(executor.llm, "output_method", "") or "")

    def _stop_for(code: str) -> AgentAction:
        messages = {
            "cancelled": "اجرا لغو شد. شواهد جمع‌شده حفظ شد و کار قابل ادامه است.",
            "consecutive_invalid": "چند پاسخ پیاپی قابل اجرا نبود. شواهد حفظ شد و مدل دیگری انتخاب نشد.",
            "no_progress": "همان اقدام بدون پیشرفت تکرار شد. شواهد حفظ شد.",
            "runtime": "سقف زمان عملیاتی این اجرا رسید. شواهد حفظ شد و نتیجه ناقص قابل ادامه است.",
            "spending": "سقف توکن این اجرا رسید. شواهد حفظ شد و نتیجه ناقص قابل ادامه است.",
        }
        return blocked_action(f"OPERATIONAL_{code.upper()}", messages.get(code, "حد عملیاتی رسید. شواهد حفظ شد."))

    while True:
        _remember_safety()
        stop = operational_stop(
            invalid_streak=invalid_streak,
            repeated=0,
            elapsed_seconds=_elapsed(),
            tokens=_tokens(),
            limits=safety,
            cancelled=_cancelled(),
        )
        if stop:
            final_action = _stop_for(stop)
            break
        if not persist():
            return _lease_lost(state, run)
        left = _budget_left(executor)
        context = build_decision_context(
            product=run.product,
            origin=run.origin_country,
            hs6=run.guessed_hs_code,
            iteration=iteration,
            max_iterations=iteration + 1,
            evidence=list(evidence_index.values()),
            sources=[{"url": url} for url in state["urls"][:12]],
            contradictions=list(state["conflicts"]),
            open_questions=list(state["open_questions"]),
            budget_left=left,
        )
        if checkpoint.get("phase_feedback"):
            context["_correction"] = str(checkpoint["phase_feedback"])
        action: AgentAction | None = None
        pending = checkpoint.get("pending_decision") or {}
        if pending.get("iteration") == iteration and pending.get("raw"):
            action = parse_model_decision(str(pending.get("raw")))
        if action is None:
            try:
                raw = guarded_model_call(
                    db,
                    run.id,
                    "decide",
                    lambda: _ask_model(executor.llm, context),
                    provider_id=str(getattr(executor.llm, "id", "llm")),
                )
                executor.budget = ensure_run_budget(db, run.id)
            except BudgetExceeded:
                iteration += 1
                continue
            except ModelCallError as exc:
                _remember_model_status(db, exc.status)
                final_action = blocked_action(
                    _MODEL_CODE.get(exc.status, "MODEL_FAILED"),
                    exc.message_fa,
                )
                break
            if getattr(executor.llm, "id", "") != "stub_llm":
                _remember_model_status(db, "Verified")
            action, note = explain_decision(raw)
            if action is None:
                invalid_streak += 1
                _remember_safety()
                if operational_stop(
                    invalid_streak=invalid_streak,
                    repeated=0,
                    elapsed_seconds=_elapsed(),
                    tokens=_tokens(),
                    limits=safety,
                    cancelled=False,
                ) == "consecutive_invalid":
                    final_action = _stop_for("consecutive_invalid")
                    break
                context["_correction"] = note
                try:
                    raw = guarded_model_call(
                        db,
                        run.id,
                        "decide",
                        lambda: _ask_model(executor.llm, context),
                        provider_id=str(getattr(executor.llm, "id", "llm")),
                    )
                    executor.budget = ensure_run_budget(db, run.id)
                except BudgetExceeded:
                    iteration += 1
                    continue
                except ModelCallError as exc:
                    _remember_model_status(db, exc.status)
                    final_action = blocked_action(
                        _MODEL_CODE.get(exc.status, "MODEL_FAILED"),
                        exc.message_fa,
                    )
                    break
                action = parse_model_decision(raw)
            if action:
                invalid_streak = 0
                checkpoint["pending_decision"] = {"iteration": iteration, "raw": raw}
                _remember_safety()
                if not persist():
                    return _lease_lost(state, run)
        if action is None:
            iteration += 1
            _remember_safety()
            continue

        await emit(
            db,
            run,
            phase="search",
            status="running",
            message_fa=action.rationale_fa or f"اقدام مدل: {action.action}",
            payload={
                "event_type": "research.decision",
                "iteration": iteration,
                "action": action.action,
                "tool": action.tool,
                "decision_source": "llm",
            },
            event_id=f"evt_{run.id}_decision_{iteration}",
        )
        if action.action in {"conclude", "ask_user", "blocked"}:
            feedback = premature_market_stop(action.action, tools_invoked, state["tool_trace"])
            if feedback:
                checkpoint["phase_feedback"] = feedback
                signature = action_signature(action.action, action.tool, action.args or {})
                if signature == last_signature:
                    repeated += 1
                else:
                    repeated = 1
                    last_signature = signature
                _remember_safety()
                repeated_cap = safety.get("max_repeated_actions")
                repeated_cap = 3 if repeated_cap is None else int(repeated_cap)
                if repeated_cap > 0 and repeated > repeated_cap:
                    final_action = blocked_action(
                        "MARKET_DISCOVERY_INCOMPLETE",
                        feedback + " شواهد جمع‌شده حفظ شد.",
                    )
                    break
                iteration += 1
                continue
            checkpoint["phase_feedback"] = ""
            final_action = action
            break
        signature = action_signature(action.action, action.tool, action.args or {})
        if signature == last_signature:
            repeated += 1
        else:
            repeated = 1
            last_signature = signature
        _remember_safety()
        repeated_cap = safety.get("max_repeated_actions")
        repeated_cap = 3 if repeated_cap is None else int(repeated_cap)
        if repeated_cap > 0 and repeated > repeated_cap:
            final_action = _stop_for("no_progress")
            break
        if action.action == "change_strategy":
            state["open_questions"].append("راهبرد تغییر کرد — منابع جایگزین لازم است")
            iteration += 1
            continue
        if action.action == "verify_conflict":
            cross = executor.execute(ToolCall(tool="cross_check", args={"claims": state["claims"]}))
            tools_invoked.append("cross_check")
            state["conflicts"].extend((cross.data or {}).get("conflicts") or [])
            state["tool_trace"].append(
                {"tool": "cross_check", "ok": cross.ok, "message_fa": cross.message_fa}
            )
            iteration += 1
            continue
        if action.action != "call_tool" or not action.tool:
            final_action = blocked_action("LLM_INVALID", "اقدام مدل قابل اجرا نبود.")
            break
        buyer_feedback = buyer_research_blocked(action.tool, run.selected_country)
        if buyer_feedback:
            checkpoint["phase_feedback"] = buyer_feedback
            signature = action_signature(action.action, action.tool, action.args or {})
            if signature == last_signature:
                repeated += 1
            else:
                repeated = 1
                last_signature = signature
            _remember_safety()
            repeated_cap = safety.get("max_repeated_actions")
            repeated_cap = 3 if repeated_cap is None else int(repeated_cap)
            if repeated_cap > 0 and repeated > repeated_cap:
                final_action = blocked_action("BUYER_RESEARCH_BLOCKED", buyer_feedback)
                break
            iteration += 1
            continue
        try:
            result = executor.execute(ToolCall(tool=action.tool, args=action.args or {}))
        except BudgetExceeded:
            iteration += 1
            continue
        tools_invoked.append(action.tool)
        state["tool_trace"].append(
            {
                "tool": action.tool,
                "ok": result.ok,
                "message_fa": result.message_fa,
                "error_code": result.error_code,
            }
        )
        for item in (result.data or {}).get("results") or []:
            if item.get("url"):
                state["urls"].append(item["url"])
        if action.tool == "fetch_page" and result.ok:
            await _absorb_page(db, run, executor, emit, state, result, action)
            evidence_index = evidence_index_for_run(db, run.id)
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
                event_id=f"evt_{run.id}_search_{iteration}",
            )
        elif not result.ok:
            state["unknowns"].append(result.message_fa)
        iteration += 1

    markets: list[Market] = []
    if final_action.action != "blocked" and final_action.market_proposals:
        markets = score_from_evidence_markets(
            final_action.market_proposals,
            product=run.product,
            evidence_index=evidence_index_for_run(db, run.id),
            sources=[
                Source(
                    url=url,
                    title=url,
                    publisher="web",
                    fetched_at="",
                    provider="free_web",
                    reliability_note="web evidence",
                )
                for url in state["urls"][:5]
            ],
        )
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
                    "period": "",
                    "published_period": "",
                    "confidence": "unknown",
                    "payload": {
                        "markets": [market.model_dump() for market in markets],
                        "data_scope": "qualitative",
                        "stop_reason": final_action.stop_reason,
                        "_provenance": {"decision_source": "llm", "run_id": run.id},
                    },
                },
            )
        )
    remember("decide")
    return await _finish(
        db, run, executor, emit, state, final_action, markets, memory_status, tools_invoked
    )


def _ask_model(llm: object, context: dict[str, Any]) -> str:
    if hasattr(llm, "decide_research_action"):
        raw = llm.decide_research_action(context)  # type: ignore[attr-defined]
        if isinstance(raw, str) and raw.strip():
            return raw
        if isinstance(raw, dict):
            return json.dumps(raw)
    if hasattr(llm, "complete_json"):
        prompt = render_decision_prompt(context)
        return str(llm.complete_json(prompt))
    return ""


async def _absorb_page(db, run, executor, emit, state, result, action) -> None:
    url = str((result.data or {}).get("url") or action.args.get("url") or "")
    text = str((result.data or {}).get("text") or "")
    if not url:
        return
    state["urls"].append(url)
    cred = executor.execute(
        ToolCall(tool="assess_credibility", args={"url": url, "title": "", "publisher": ""})
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
    for claim in (extracted.data or {}).get("claims") or []:
        state["claims"].append(claim)
        try:
            record_claim(
                db,
                run_id=run.id,
                statement=str(claim.get("statement") or "")[:2000],
                source_url=url,
                data_kind="estimate",
                hs_scope=run.guessed_hs_code,
                product_scope=run.product,
                period=claim.get("period"),
                confidence="unknown",
            )
        except ValueError:
            continue
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
                reliability_note=str((cred.data or {}).get("level") or "unknown"),
            )
        ],
        event_id=f"evt_{run.id}_page_{abs(hash(url)) % 10**8}",
    )


def _lease_lost(state: dict[str, Any], run: Run) -> dict[str, Any]:
    action = blocked_action("LEASE_LOST", "اجاره کار از دست رفت. checkpoint حفظ شد و کار قابل ادامه است.")
    return {
        "markets": [],
        "recommended": [],
        "risky": [],
        "sources": [],
        "data_scope": "qualitative",
        "trade_meta": {"quality_status": "unavailable", "source_name": "blocked", "warnings": []},
        "memory_status": "miss",
        "plan": {"questions": state.get("open_questions") or [], "notes_fa": action.rationale_fa, "tools_needed": []},
        "tool_trace": state.get("tool_trace") or [],
        "stop_reason": "LEASE_LOST",
        "unknowns": action.unknowns,
        "conflicts": [],
        "tools_invoked": [],
        "decision_source": "blocked",
    }


async def _finish(db, run, executor, emit, state, final_action, markets, memory_status, tools_invoked):
    del executor
    recommended = [
        market
        for market in markets
        if any(item.key == "recommendation" and item.value == "recommended" for item in market.metrics)
    ]
    risky = [
        market
        for market in markets
        if any(item.key == "recommendation" and item.value == "risky" for item in market.metrics)
    ]
    run.markets_json = json.dumps([market.model_dump() for market in markets], ensure_ascii=False)
    db.commit()
    blocked = final_action.action == "blocked" or final_action.stop_reason in {
        "LLM_UNAVAILABLE",
        "LLM_INVALID",
        "LEASE_LOST",
    }
    status = "partial" if blocked or not recommended else "completed"
    message = final_action.rationale_fa
    if markets and not blocked:
        message = (
            f"پایان حلقه مدل: {len(recommended)} پیشنهاد، {len(risky)} پرریسک — {final_action.rationale_fa}"
        )
    tokens = int(state.get("tokens_used") or 0)
    if tokens:
        message += f" — توکن: {tokens}"
        cost = float(state.get("estimated_cost_usd") or 0)
        if cost:
            message += f" — هزینه برآوردی: ${cost:.4f}"
    await emit(
        db,
        run,
        phase="market_compare",
        status=status,
        message_fa=message,
        payload={
            "event_type": "research.blocked" if blocked else ("market.ranked" if markets else "task.partial"),
            "stop_reason": final_action.stop_reason,
            "recoverable": bool(final_action.recoverable) if blocked else False,
            "decision_source": final_action.decision_source,
            "recommended": [market.country_code for market in recommended],
            "risky": [market.country_code for market in risky],
            "tool_trace": state.get("tool_trace") or [],
            "memory_status": memory_status,
            "conflicts": list(state.get("conflicts") or []) + list(final_action.conflicts or []),
            "unknowns": list(
                dict.fromkeys([*(state.get("unknowns") or []), *final_action.unknowns])
            ),
            "tools_invoked": tools_invoked,
            "tokens_used": int(state.get("tokens_used") or 0),
            "estimated_cost_usd": float(state.get("estimated_cost_usd") or 0),
            "output_method": state.get("output_method") or "",
        },
        error_code=final_action.blocked_code or final_action.stop_reason if blocked or not markets else None,
        event_id=f"evt_{run.id}_market_compare",
    )
    sources = [
        Source(
            url=url,
            title=url,
            publisher="web",
            fetched_at="",
            provider="free_web",
            reliability_note="discovered during research",
        )
        for url in list(dict.fromkeys(state.get("urls") or []))[:12]
    ]
    return {
        "markets": markets,
        "recommended": recommended,
        "risky": risky,
        "sources": sources,
        "data_scope": "qualitative",
        "trade_meta": {
            "quality_status": "partial" if markets and not blocked else "unavailable",
            "source_name": "cited evidence" if markets else "blocked" if blocked else "no evidence",
            "warnings": list(state.get("conflicts") or []) + list(state.get("unknowns") or []),
        },
        "memory_status": memory_status,
        "plan": {
            "questions": state.get("open_questions") or [],
            "notes_fa": final_action.rationale_fa,
            "tools_needed": sorted({item["tool"] for item in state.get("tool_trace") or [] if item.get("tool")}),
        },
        "tool_trace": state.get("tool_trace") or [],
        "stop_reason": final_action.stop_reason,
        "unknowns": list(dict.fromkeys([*(state.get("unknowns") or []), *final_action.unknowns])),
        "conflicts": list(state.get("conflicts") or []) + list(final_action.conflicts or []),
        "tools_invoked": tools_invoked,
        "decision_source": final_action.decision_source,
    }
