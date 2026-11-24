"""Research loop. The active LLM decides, or the run is blocked. No heuristic substitute."""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Awaitable, Callable

from sqlalchemy.orm import Session

from app.agents.decision_schema import SYNTHESIS_ACTIONS
from app.agents.llm_decide import (
    AgentAction,
    blocked_action,
    build_decision_context,
    explain_decision,
    llm_is_research_decision_maker,
    parse_model_decision,
    pending_steps,
)
from app.agents.loop_safety import (
    action_signature,
    active_elapsed,
    effective_limits,
    operational_stop,
    runtime_stop_message,
)
from app.agents.hs_code import hs_codes_in_text
from app.agents.observations import (
    absorb_search_results,
    compact_evidence,
    context_sources,
    evidence_context,
    evidence_coverage,
    load_observations,
    mark_pages,
    normalize_url,
    observation_sources,
    page_progress_fa,
    page_read_status,
    processed_source,
    research_counts,
    search_progress_fa,
    trade_claim_key,
)
from app.agents.research_phase import (
    ALREADY_PROCESSED_FEEDBACK,
    FRUITLESS_SEARCH_FEEDBACK,
    buyer_research_blocked,
    premature_market_stop,
    shortlist_evidence,
    unread_sources_block_conclude,
)
from app.agents.market_scorer import score_from_evidence_markets, validate_market_proposal
from app.agents.tool_contracts import ToolCall
from app.evidence.store import evidence_index_for_run, record_claim
from app.jobs.durable import renew_lease, write_checkpoint
from app.models.entities import Run
from app.schemas.contracts import Market, Source
from app.providers.keyed import ModelCallError
from app.tools.budget import BudgetExceeded, ensure_run_budget, guarded_model_call
from app.tools.executor import ToolExecutor
from app.tools.extract import canonical_claim_text, country_code, country_mentions, trade_fields

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
    session_started = time.monotonic()
    checkpoint.setdefault("version", 2)
    completed = list(checkpoint.get("completed_steps") or [])
    legacy_state = checkpoint.get("state") or {}
    state: dict[str, Any] = dict(legacy_state)
    state.setdefault("tool_trace", [])
    state.setdefault("seen_claim_ids", [])
    state.setdefault("candidates", {})
    state.setdefault("resolved_questions", {})
    state.setdefault("action_outcomes", {})
    state.setdefault("recent_actions", [])
    state.setdefault("urls", [])
    loaded = load_observations(db, run.id)
    if loaded:
        state["observations"] = loaded
    elif "observations" not in state:
        if state.get("urls"):
            absorb_search_results(
                state,
                [{"url": url} for url in state["urls"]],
                run_id=run.id,
                db=db,
            )
        else:
            state["observations"] = []
    else:
        state.setdefault("observations", [])
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
    fruitless = int(checkpoint.get("fruitless_searches") or 0)
    unread_nudges = int(checkpoint.get("unread_nudges") or 0)

    def persist() -> bool:
        checkpoint["version"] = 2
        checkpoint["decision_iteration"] = iteration
        checkpoint["completed_steps"] = completed
        if state.get("memory_status"):
            checkpoint["memory_status"] = state["memory_status"]
        checkpoint["state"] = {
            "tool_trace": state["tool_trace"][-30:],
            "conflicts": state["conflicts"][:12],
            "unknowns": state["unknowns"][:12],
            "open_questions": state["open_questions"][:8],
            "seen_claim_ids": state["seen_claim_ids"],
            "candidates": state["candidates"],
            "resolved_questions": state["resolved_questions"],
            "action_outcomes": dict(list(state["action_outcomes"].items())[-40:]),
            "recent_actions": state["recent_actions"][-4:],
        }
        for key in ("claims", "urls"):
            if key in legacy_state:
                checkpoint["state"][key] = legacy_state[key]
        checkpoint["tools_invoked"] = tools_invoked[-40:]
        checkpoint["fruitless_searches"] = fruitless
        checkpoint["unread_nudges"] = unread_nudges
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
        classify = await asyncio.to_thread(
            executor.execute,
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

    final_action: AgentAction | None = None
    evidence_index = evidence_index_for_run(db, run.id)
    from app.services.admin_service import read_safety

    safety = read_safety(db)
    limits = effective_limits(safety)
    state["effective_limits"] = limits
    checkpoint["effective_limits"] = limits
    tokens_before = int(checkpoint.get("tokens_used") or 0)
    carried_seconds = float(checkpoint.get("active_seconds") or 0)
    invalid_streak = int(checkpoint.get("invalid_streak") or 0)
    repeated_cap = limits["max_repeated_actions"]
    carried_cost = float(checkpoint.get("estimated_cost_usd") or 0)
    carried_profiles = list(checkpoint.get("model_calls") or [])
    evidence_selection: dict = checkpoint.get("evidence_selection") or {}

    await emit(
        db,
        run,
        phase="search",
        status="running",
        message_fa="حلقه تحقیق — تصمیم با مدل فعال",
        payload={
            "event_type": "research.loop_start",
            "decision_source": "llm",
            "effective_limits": limits,
        },
        event_id=f"evt_{run.id}_loop_start",
    )

    def _elapsed() -> float:
        return active_elapsed(carried_seconds, session_started, time.monotonic())

    def _tokens() -> int:
        return tokens_before + int(getattr(executor.llm, "tokens_used", 0) or 0)

    def _cancelled() -> bool:
        db.refresh(run)
        return run.status == "cancelled"

    def _remember_safety() -> None:
        checkpoint["invalid_streak"] = invalid_streak
        checkpoint["active_seconds"] = _elapsed()
        state["active_seconds"] = round(_elapsed(), 1)
        checkpoint["tokens_used"] = _tokens()
        state["tokens_used"] = _tokens()
        state["estimated_cost_usd"] = carried_cost + float(getattr(executor.llm, "cost_usd", 0) or 0)
        checkpoint["estimated_cost_usd"] = state["estimated_cost_usd"]
        state["model_calls"] = [*carried_profiles, *getattr(executor.llm, "model_calls", [])]
        checkpoint["model_calls"] = state["model_calls"]
        state["output_method"] = str(getattr(executor.llm, "output_method", "") or "")

    def _stop_for(code: str) -> AgentAction:
        elapsed = round(_elapsed(), 1)
        token_cap = limits["max_run_tokens"]
        messages = {
            "cancelled": "اجرا لغو شد. شواهد جمع‌شده حفظ شد و کار قابل ادامه است.",
            "consecutive_invalid": (
                f"چند پاسخ پیاپی قابل اجرا نبود (سقف {limits['max_consecutive_invalid']}). "
                "شواهد حفظ شد و مدل دیگری انتخاب نشد."
            ),
            "no_progress": (
                f"همان اقدام بدون پیشرفت تکرار شد (سقف {limits['max_repeated_actions']}). شواهد حفظ شد."
            ),
            "runtime": runtime_stop_message(elapsed, limits["max_runtime_seconds"]),
            "spending": (
                f"توقف به دلیل سقف توکن: {_tokens()} از {token_cap}. شواهد و نقطه ادامه حفظ شد."
            ),
        }
        state["last_stop"] = {
            "code": code,
            "active_seconds": elapsed,
            "tokens_used": _tokens(),
            "effective_limits": limits,
        }
        checkpoint["last_stop"] = state["last_stop"]
        return blocked_action(
            f"OPERATIONAL_{code.upper()}",
            messages.get(code, "حد عملیاتی رسید. شواهد حفظ شد."),
        )

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
        evidence_rows = compact_evidence(evidence_index)
        observations = list(state.get("observations") or [])
        seen_ids = {str(item) for item in (state.get("seen_claim_ids") or [])}
        invalid_cap = limits["max_consecutive_invalid"]
        shortlist = shortlist_evidence(evidence_rows, state["candidates"], run.origin_country, run.guessed_hs_code)
        synthesis = bool(evidence_rows) and (
            bool(shortlist or checkpoint.get("synthesis_requested"))
            or (invalid_cap > 1 and invalid_streak == invalid_cap - 1)
        )
        mode = "synthesis" if synthesis else "research"
        if synthesis:
            cited = {ref for candidate in state["candidates"].values() for ref in candidate["evidence_ids"]}
            evidence_rows = sorted(evidence_rows, key=lambda row: (row["id"] not in shortlist, row["id"] not in cited))
            evidence_selection = {}
        previews = evidence_context(evidence_rows, set() if synthesis else seen_ids, evidence_selection)
        new_ids = [row["id"] for row in previews if row["id"] not in seen_ids]
        if not (checkpoint.get("pending_decision") or {}).get("iteration") == iteration:
            state["seen_claim_ids"] += new_ids
        evidence_selection = {}
        context = build_decision_context(
            product=run.product,
            origin=run.origin_country,
            hs6=run.guessed_hs_code,
            iteration=iteration,
            max_iterations=iteration + 1,
            evidence=previews,
            sources=[] if synthesis else context_sources(observations),
            contradictions=list(state["conflicts"]),
            open_questions=list(state["open_questions"]),
            budget_left=left,
            research_state=research_counts(observations, evidence_rows),
            schema_detail="full" if iteration == 0 else "compact",
            new_evidence_ids=new_ids,
        )
        context["decision_mode"] = mode
        if synthesis:
            context["synthesis_reason"] = "market_shortlist_ready" if shortlist else "recovery"
            context["allowed_actions"] = list(SYNTHESIS_ACTIONS)
            context["allowlisted_tools"] = []
            context["tool_schema"] = {}
        context["coverage"] = evidence_coverage(evidence_rows, state["candidates"])
        context["candidates"] = [
            {key: value for key, value in candidate.items() if key != "risks"}
            for candidate in state["candidates"].values()
        ]
        context["questions"] = {
            f"q{i}": {"question": question, "evidence_ids": state["resolved_questions"].get(f"q{i}", [])}
            for i, question in enumerate(state["open_questions"], 1)
        }
        context.pop("open_questions", None)
        context["recent_actions"] = state["recent_actions"][-3:]
        context.pop("max_iterations", None)
        context.pop("budget_left", None)
        if checkpoint.get("phase_feedback"):
            context["_correction"] = str(checkpoint["phase_feedback"])
            context["recent_actions"] = [
                {key: value for key, value in item.items() if key != "message" or value != context["_correction"]}
                for item in context["recent_actions"]
            ]
        if checkpoint.get("candidate_feedback"):
            context["rejected_proposals"] = checkpoint["candidate_feedback"]
        action: AgentAction | None = None
        pending = checkpoint.get("pending_decision") or {}
        if pending.get("iteration") == iteration and pending.get("mode", "research") == mode and pending.get("raw"):
            action = parse_model_decision(str(pending.get("raw")))
        if action is None:
            try:
                raw = await asyncio.to_thread(
                    guarded_model_call,
                    db,
                    run.id,
                    "synthesize" if synthesis else "decide",
                    lambda: _ask_model(executor.llm, context),
                    provider_id=str(getattr(executor.llm, "id", "llm")),
                )
                executor.budget = ensure_run_budget(db, run.id)
            except BudgetExceeded:
                final_action = _stop_for("spending")
                break
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
            if synthesis and action is not None and action.action not in SYNTHESIS_ACTIONS:
                action = None
                note = "مهلت جمع‌بندی است. conclude یا ask_user را بر اساس شواهد انتخاب کنید."
            if action is None:
                invalid_streak += 1
                checkpoint.pop("synthesis_requested", None)
                checkpoint["phase_feedback"] = note
                await emit(
                    db, run, phase="search", status="running", message_fa=note,
                    payload={"event_type": "research.decision_invalid", "iteration": iteration,
                             "decision_mode": mode,
                             "visible_evidence_ids": [row["id"] for row in previews]},
                    event_id=f"evt_{run.id}_invalid_{iteration}",
                )
            if action:
                checkpoint["pending_decision"] = {"iteration": iteration, "raw": raw, "mode": mode}
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
                "decision_mode": mode,
                **({"synthesis_reason": context["synthesis_reason"]} if synthesis else {}),
                "decision_source": "llm",
                "visible_evidence_ids": [row["id"] for row in previews],
                "new_evidence_ids": new_ids,
                "candidate_codes": list(state["candidates"]),
            },
            event_id=f"evt_{run.id}_decision_{iteration}",
        )
        changed_candidates = []
        candidate_feedback = []
        state["unknowns"] = list(dict.fromkeys([*state["unknowns"], *action.unknowns]))[-12:]
        state["conflicts"] = list(dict.fromkeys([*state["conflicts"], *action.conflicts]))[-12:]
        visible = set(state["seen_claim_ids"])
        for proposal in action.market_proposals:
            candidate, reason = validate_market_proposal(
                proposal, product=run.product, origin=run.origin_country,
                evidence_index=evidence_index, visible=visible,
            )
            if not candidate:
                candidate_feedback.append({"country": str(proposal.get("country_code", ""))[:32], "reason": reason})
                continue
            code = candidate["country_code"]
            previous = state["candidates"].get(code) or {}
            if candidate != previous:
                improved = (
                    not previous
                    or bool(set(candidate["evidence_ids"]) - set(previous["evidence_ids"]))
                    or bool(
                        {(item["criterion"], ref) for item in candidate["criteria"] for ref in item["evidence_ids"]}
                        - {(item["criterion"], ref) for item in previous["criteria"] for ref in item["evidence_ids"]}
                    )
                )
                state["candidates"][code] = candidate
                changed_candidates.append({**candidate, "coverage_improved": improved})

        resolved = []
        for resolution in _resolve_questions(action.args, context["questions"], visible):
            key, refs = resolution
            if key not in state["resolved_questions"]:
                state["resolved_questions"][key] = refs
                resolved.append(key)

        args = {key: value for key, value in action.args.items() if key != "resolved_questions"}
        tool = action.tool
        source_id = args.get("source_id") if tool == "fetch_source" else None
        if source_id:
            source = next((row for row in observations if row.get("id") == source_id), None)
            if source:
                tool, args = "fetch_page", {"url": source["url"]}
        if tool in {"fetch_page", "extract_claims"}:
            tool = "fetch_page"
            target_url = str(args.get("url") or "")
            args = {"url": normalize_url(target_url) or target_url}
        signature = action_signature(action.action, tool, args)
        previous_outcome = state["action_outcomes"].get(signature) or {}
        feedback = ""
        new_sources = 0
        new_claims = 0
        error_code = None
        suppressed = False

        if action.action in {"conclude", "ask_user"}:
            if not evidence_rows:
                feedback = premature_market_stop(action.action, tools_invoked, state["tool_trace"]) or ""
            if not feedback and unread_nudges < 1:
                feedback = unread_sources_block_conclude(state["observations"], len(evidence_rows)) or ""
                unread_nudges += int(bool(feedback))
            if not synthesis and not feedback and candidate_feedback and not state["candidates"] and not previous_outcome:
                feedback = "Market proposals were rejected. Review the rejection details and cite destination-specific claims."
            if not feedback:
                action.stop_reason = action.stop_reason or (
                    "supported_markets" if state["candidates"] else "insufficient_evidence"
                )
                final_action = action
            else:
                error_code = "SYNTHESIS_NOT_READY"
        elif action.action == "change_strategy":
            feedback = "Choose a different research action or synthesize the evidence already available."
            error_code = "STRATEGY_NEEDS_ACTION"
        elif action.action == "verify_conflict":
            result = executor.execute(ToolCall(tool="cross_check", args={"claims": evidence_rows}))
            tools_invoked.append("cross_check")
            state["conflicts"] = list(dict.fromkeys([*state["conflicts"], *((result.data or {}).get("conflicts") or [])]))
            feedback = result.message_fa
            error_code = result.error_code
        elif tool:
            prior = processed_source(state, args.get("url", "")) if tool == "fetch_page" else None
            gate = buyer_research_blocked(tool, run.selected_country)
            if gate:
                feedback, error_code = gate, "BUYER_RESEARCH_BLOCKED"
            elif tool == "fetch_source":
                feedback = "شناسهٔ منبع یافت نشد. یک source_id از فهرست CONTEXT.sources انتخاب کنید."
                error_code = "UNKNOWN_SOURCE_ID"
            elif prior:
                feedback = f"{ALREADY_PROCESSED_FEEDBACK} {prior['url']}: {prior['status']}."
                error_code = "SOURCE_ALREADY_PROCESSED"
                message_fa, event_type = page_progress_fa(0, status="already_processed")
                await emit(
                    db, run, phase="trade_stats", status="running", message_fa=message_fa,
                    payload={"event_type": event_type, "url": prior["url"], "source_status": prior["status"],
                             "claim_count": prior.get("claim_count", 0)},
                    event_id=f"evt_{run.id}_seen_{iteration}",
                )
            elif repeated_cap > 0 and int(previous_outcome.get("no_progress") or 0) >= repeated_cap:
                feedback = f"Action skipped after repeated no-progress outcomes: {previous_outcome['message']}"
                error_code = previous_outcome["error_code"] or "ACTION_EXHAUSTED"
                suppressed = True
            elif tool == "read_evidence":
                evidence_selection = args or {"offset": 0}
                found = evidence_context(evidence_rows, visible, evidence_selection)
                page_key = "|".join(sorted(row["id"] for row in found))
                previous_pages = checkpoint.get("evidence_read_pages") or []
                if not found:
                    feedback, error_code = "هیچ شاهدی با این انتخاب تطبیق نداشت.", "NO_MATCHING_EVIDENCE"
                elif page_key in previous_pages:
                    evidence_selection = {}
                    feedback = "متن همین شاهدها قبلاً نمایش داده شد. از شناسه‌های موجود استفاده کنید یا شاهد متفاوتی بخوانید."
                    error_code = "EVIDENCE_ALREADY_REVIEWED"
                else:
                    checkpoint["evidence_read_pages"] = [*previous_pages, page_key][-16:]
                    feedback = f"متن {len(found)} شاهد برای مرور انتخاب شد."
            elif tool == "save_evidence" and args.get("kind") == "market_stats":
                feedback, error_code = "Market memory is written from validated research results.", "MARKET_MEMORY_MANAGED"
            else:
                result = await asyncio.to_thread(executor.execute, ToolCall(tool=tool, args=args))
                tools_invoked.append(tool)
                feedback = result.message_fa
                error_code = result.error_code
                if tool == "fetch_page":
                    if result.ok:
                        terms = action.args.get("product_terms")
                        terms = [value[:60] for value in terms[:4] if isinstance(value, str)] if isinstance(terms, list) else []
                        new_claims, feedback, error_code = await _absorb_page(
                            db, run, executor, emit, state, result, args["url"], terms, iteration,
                        )
                        evidence_index = evidence_index_for_run(db, run.id)
                    else:
                        absorb_search_results(state, [{"url": args["url"]}], run_id=run.id, db=db)
                        mark_pages(state, [args["url"]], status="inaccessible", claim_count=0, db=db)
                        await emit(
                            db, run, phase="trade_stats", status="running", message_fa=feedback,
                            payload={"event_type": "research.source_inaccessible", "url": args["url"],
                                     "source_status": "inaccessible", "error_code": error_code},
                            event_id=f"evt_{run.id}_fetch_failed_{iteration}",
                        )
                elif tool == "search_web":
                    summary = absorb_search_results(
                        state, list((result.data or {}).get("results") or []), run_id=run.id, db=db,
                    )
                    new_sources = summary["new_useful"]
                    fruitless = 0 if new_sources else fruitless + 1
                    feedback = search_progress_fa(summary["total"], new_sources, summary["thin"]) if result.ok else feedback
                    await emit(
                        db, run, phase="search", status="running", message_fa=feedback,
                        payload={"event_type": "research.search_done", "result_count": summary["total"],
                                 "new_sources": new_sources, "thin_results": summary["thin"],
                                 "verified_claims": len(evidence_rows), "error_code": error_code,
                                 "discovered": [{"id": row["id"], "url": row["url"]} for row in summary["added"]]},
                        source_refs=observation_sources(summary["added"])[:8],
                        event_id=f"evt_{run.id}_search_{iteration}",
                    )
                    if not new_sources:
                        feedback = f"{feedback} {FRUITLESS_SEARCH_FEEDBACK}"
                        error_code = error_code or "NO_NEW_SOURCES"

        progress = {
            "new_useful_sources": new_sources,
            "new_validated_claims": new_claims,
            "questions_resolved": len(resolved),
            "market_coverage_improved": sum(c["coverage_improved"] for c in changed_candidates),
        }
        advanced = any(progress.values())
        no_progress = 0 if advanced else int(previous_outcome.get("no_progress") or 0) + 1
        actionable = any(row["status"] in {"unread", "fetched"} and row["useful"] for row in state["observations"])
        if advanced:
            state["action_outcomes"].clear()
            fruitless = 0
        ignored_failure = suppressed or error_code in {
            "SOURCE_ALREADY_PROCESSED", "BUYER_RESEARCH_BLOCKED", "STRATEGY_NEEDS_ACTION",
        }
        invalid_streak = invalid_streak + 1 if ignored_failure and no_progress > repeated_cap > 0 else 0
        checkpoint.pop("synthesis_requested", None)
        if not final_action and not advanced:
            if not synthesis and evidence_rows and (
                (error_code and 0 < repeated_cap <= no_progress)
                or (tool == "search_web" and 0 < limits["max_fruitless_searches"] <= fruitless)
            ):
                checkpoint["synthesis_requested"] = True
            if tool == "search_web" and 0 < limits["max_fruitless_searches"] <= fruitless and not (actionable or evidence_rows):
                final_action = blocked_action("NO_NEW_SOURCES", feedback)
            elif repeated_cap > 0 and no_progress > repeated_cap and not (actionable or evidence_rows):
                if feedback and action.action in {"conclude", "ask_user"}:
                    final_action = blocked_action("MARKET_DISCOVERY_INCOMPLETE", feedback)
                elif error_code == "BUYER_RESEARCH_BLOCKED":
                    final_action = blocked_action(error_code, feedback)
                else:
                    final_action = _stop_for("no_progress")
        outcome = {"message": feedback[:500], "error_code": error_code, "no_progress": no_progress}
        state["action_outcomes"].pop(signature, None)
        state["action_outcomes"][signature] = outcome
        outcome_detail = {"action": action.action, "tool": tool, "query": str(args.get("query") or "")[:180],
                          "url": str(args.get("url") or "")[:2048], **outcome}
        if source_id:
            outcome_detail["source_id"] = source_id
        state["recent_actions"].append(outcome_detail)
        state["recent_actions"] = state["recent_actions"][-4:]
        state["tool_trace"].append({"tool": tool, "ok": not error_code, "message_fa": feedback, "error_code": error_code})
        checkpoint["phase_feedback"] = feedback if error_code or candidate_feedback else ""
        checkpoint["candidate_feedback"] = candidate_feedback
        checkpoint["evidence_selection"] = evidence_selection
        await emit(
            db, run, phase="search", status="running", message_fa=feedback or action.rationale_fa,
            payload={"event_type": "research.outcome", "iteration": iteration, **outcome_detail,
                     "progress": progress, "resolved_questions": resolved,
                     "candidate_updates": changed_candidates, "rejected_proposals": candidate_feedback,
                     "model_stop_reason": action.stop_reason},
            event_id=f"evt_{run.id}_outcome_{iteration}",
        )
        iteration += 1
        checkpoint.pop("pending_decision", None)
        _remember_safety()
        if not persist():
            return _lease_lost(state, run)
        if final_action:
            break

    final_candidates = list(state["candidates"].values())
    if final_action.action == "conclude" and final_action.market_proposals:
        selected = [
            country_code(str(proposal.get("country_code") or ""))
            for proposal in final_action.market_proposals
        ]
        chosen = [state["candidates"][code] for code in dict.fromkeys(selected) if code in state["candidates"]]
        final_candidates = chosen or final_candidates
    markets = score_from_evidence_markets(
        final_candidates, product=run.product,
        evidence_index=evidence_index_for_run(db, run.id),
        sources=observation_sources(state["observations"], limit=None),
    )
    if markets and final_action.action == "conclude":
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
    checkpoint["termination"] = {
        "action": final_action.action,
        "reason": final_action.stop_reason,
        "market_codes": [market.country_code for market in markets],
    }
    _remember_safety()
    if not persist():
        return _lease_lost(state, run)
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
    return ""


def _resolve_questions(args, questions, visible):
    updates = args.get("resolved_questions")
    if not isinstance(updates, list):
        return
    for item in updates:
        if not isinstance(item, dict):
            continue
        key, refs = item.get("id"), item.get("evidence_ids")
        if isinstance(key, str) and key in questions and isinstance(refs, list) and refs:
            if all(isinstance(ref, str) and ref in visible for ref in refs):
                yield key, list(dict.fromkeys(refs))


def _store_claims(db, run, state, url: str, claims: list) -> int:
    url = normalize_url(url)
    if not url:
        return 0
    rows = evidence_index_for_run(db, run.id).values()
    seen = {
        canonical_claim_text(row["statement"])
        for row in rows
        if row and normalize_url(row.get("source_url") or "") == url
    }
    seen_trade = {key for row in rows if (key := trade_claim_key(row)) is not None}
    source_id = next(
        (row["id"] for row in state.get("observations", []) if row.get("url_key") == url),
        None,
    )
    stored = 0
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        statement = " ".join(str(claim.get("statement") or "").split())[:2000]
        key = canonical_claim_text(statement)
        if not key or key in seen:
            continue
        hs_scope = str(claim.get("hs_scope") or "")
        trade = trade_fields(statement)
        if not hs_scope and trade:
            hs_scope = run.guessed_hs_code or ""
        if hs_scope not in hs_codes_in_text(statement) or hs_scope != run.guessed_hs_code:
            hs_scope = None
        trade_key = trade_claim_key({"trade": trade, "hs_scope": hs_scope})
        if trade_key is not None and trade_key in seen_trade:
            continue
        country = country_code(str(claim.get("country") or ""))
        if not country:
            mentions = country_mentions(statement) - {country_code(run.origin_country)}
            country = next(iter(mentions)) if len(mentions) == 1 else None
        period = str(claim.get("period") or "")
        if not re.fullmatch(r"(19|20)\d{2}", period) or period not in statement:
            period = None
        record_claim(
            db, run_id=run.id, statement=statement, source_url=url,
            data_kind="estimate", hs_scope=hs_scope, country_scope=country,
            product_scope=run.product, period=period, confidence="unknown", evidence_id=source_id,
        )
        seen.add(key)
        if trade_key is not None:
            seen_trade.add(trade_key)
        stored += 1
    return stored


async def _absorb_page(db, run, executor, emit, state, result, requested, terms, iteration):
    page = result.data or {}
    url = normalize_url(str(page.get("url") or requested))
    if not url:
        return 0, "Fetched page had no usable source URL.", "INVALID_SOURCE_URL"
    text = str(page.get("text") or "")
    absorb_search_results(
        state, [{"url": requested}, {"url": url, "provider": "fetch_page"}], run_id=run.id, db=db,
    )
    prior = processed_source(state, url)
    mark_pages(state, [requested], status="fetched", claim_count=0, db=db)
    if not prior:
        mark_pages(state, [url], status="fetched", claim_count=0, db=db)
    await emit(
        db, run, phase="trade_stats", status="running", message_fa=result.message_fa,
        payload={"event_type": "research.page_fetched", "url": url, "requested_url": requested, "source_status": "fetched"},
        event_id=f"evt_{run.id}_fetched_{iteration}",
    )
    if prior:
        mark_pages(state, [requested], status=prior["status"], claim_count=prior.get("claim_count", 0), db=db)
        return 0, f"Redirected to a previously processed source: {prior['status']}.", "SOURCE_ALREADY_PROCESSED"
    extracted = await asyncio.to_thread(
        executor.execute,
        ToolCall(tool="extract_claims", args={
            "text": text, "url": url, "product": run.product, "origin": run.origin_country,
            "tables": page.get("tables") or [], "hs_code": run.guessed_hs_code, "product_terms": terms,
        })
    )
    claims = list((extracted.data or {}).get("claims") or []) if extracted.ok else []
    stored = _store_claims(db, run, state, url, claims)
    ids = [row["id"] for row in compact_evidence(evidence_index_for_run(db, run.id)) if row["source_url"] == url]
    status = page_read_status(
        stored=len(ids), raw_claims=len(claims),
        extract_outcome=str((extracted.data or {}).get("outcome") or "") if extracted.ok else "failed",
    )
    if status in {"rejected", "extraction_failed"}:
        status = "extraction_failed"
    mark_pages(state, [requested, url], status=status, claim_count=len(ids), db=db)
    message_fa, event_type = page_progress_fa(stored, status=status)
    await emit(
        db, run, phase="trade_stats", status="running", message_fa=message_fa,
        payload={"event_type": event_type, "url": url, "requested_url": requested,
                 "claim_count": stored, "claim_ids": ids, "extract_outcome": status,
                 "error_code": extracted.error_code, "raw_claim_count": len(claims),
                 "table_rows_seen": (extracted.data or {}).get("table_rows_seen")},
        source_refs=[Source(url=url, title=url, publisher="web", fetched_at=str(page.get("fetched_at") or ""),
                            provider="fetch_page", reliability_note=f"obs:{status}")],
        event_id=f"evt_{run.id}_page_{iteration}",
    )
    if status == "extraction_failed":
        message_fa += " (extraction_failed)"
    return stored, f"{message_fa} {extracted.message_fa}", extracted.error_code


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
    evidence_rows = compact_evidence(evidence_index_for_run(db, run.id))
    sources = observation_sources(state.get("observations"))
    research_audit = {
        "sources": [
            {key: source.get(key) for key in ("id", "url", "title", "status", "claim_count")}
            for source in state["observations"]
        ],
        "claims": evidence_rows,
        "candidates": list(state["candidates"].values()),
        "coverage": evidence_coverage(evidence_rows, state["candidates"]),
        "resolved_questions": state["resolved_questions"],
        "unresolved_questions": {
            f"q{i}": question for i, question in enumerate(state["open_questions"], 1)
            if f"q{i}" not in state["resolved_questions"]
        },
        "model_calls": state.get("model_calls") or getattr(executor.llm, "model_calls", []),
    }
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
    watch = [
        market
        for market in markets
        if any(item.key == "recommendation" and item.value == "watch" for item in market.metrics)
    ]
    db.refresh(run)
    run.markets_json = json.dumps([market.model_dump() for market in markets], ensure_ascii=False)
    db.commit()
    blocked = final_action.action == "blocked" or final_action.stop_reason in {
        "LLM_UNAVAILABLE",
        "LLM_INVALID",
        "LEASE_LOST",
    }
    provisional = bool(markets and final_action.action != "conclude")
    status = "partial" if blocked or provisional or not markets else "completed"
    message = final_action.rationale_fa
    if markets and not blocked:
        message = (
            f"پایان حلقه مدل: {len(recommended)} پیشنهاد، {len(risky)} پرریسک، "
            f"{len(watch)} کیفی نامطمئن — {final_action.rationale_fa}"
        )
    tokens = int(state.get("tokens_used") or getattr(executor.llm, "tokens_used", 0) or 0)
    if tokens:
        message += f" — توکن: {tokens}"
    cost = float(state.get("estimated_cost_usd") or getattr(executor.llm, "cost_usd", 0) or 0)
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
            "provisional": provisional,
            "decision_source": final_action.decision_source,
            "recommended": [market.country_code for market in recommended],
            "risky": [market.country_code for market in risky],
            "watch": [market.country_code for market in watch],
            "active_seconds": state.get("active_seconds"),
            "effective_limits": state.get("effective_limits") or {},
            "stop_detail": state.get("last_stop") or {},
            "claim_count": len(evidence_rows),
            "research_audit": research_audit,
            "tool_trace": state.get("tool_trace") or [],
            "memory_status": memory_status,
            "conflicts": list(state.get("conflicts") or []) + list(final_action.conflicts or []),
            "unknowns": list(
                dict.fromkeys([*(state.get("unknowns") or []), *final_action.unknowns])
            ),
            "tools_invoked": tools_invoked,
            "tokens_used": tokens,
            "estimated_cost_usd": cost,
            "provider_reported_cost": any(
                "cost_micros" in call.get("usage", {}) for call in research_audit["model_calls"]
            ),
            "output_method": state.get("output_method") or "",
        },
        error_code=final_action.blocked_code or final_action.stop_reason if blocked or not markets else None,
        event_id=f"evt_{run.id}_market_compare",
    )
    if not sources:
        sources = [
            Source(
                url=url,
                title=url,
                publisher="web",
                fetched_at="",
                provider="free_web",
                reliability_note="obs:unread",
            )
            for url in list(dict.fromkeys(state.get("urls") or []))[:12]
        ]
    return {
        "markets": markets,
        "recommended": recommended,
        "risky": risky,
        "watch": watch,
        "effective_limits": state.get("effective_limits") or {},
        "active_seconds": state.get("active_seconds"),
        "stop_detail": state.get("last_stop") or {},
        "sources": sources,
        "data_scope": "qualitative",
        "trade_meta": {
            "quality_status": "partial" if markets else "unavailable",
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
        "provisional": provisional,
        "observation_counts": research_counts(
            state.get("observations"),
            evidence_rows,
        ),
    }
