"""Smart orchestrator — durable stages, agent research, human market gate."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.research_runner import run_market_research
from app.agents.state_machine import ui_phase
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.events.broadcaster import broadcaster
from app.events.store import append_event
from app.jobs.durable import claim_task, create_task, finish_task, latest_task_for_run, recover_stale_leases
from app.models.entities import Run
from app.schemas.contracts import Report, RunEventOut, Source
from app.tools.budget import ensure_global_budget, ensure_run_budget
from app.tools.executor import ToolExecutor

_pipeline_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="nova-agentic")
_WORKER_ID = f"worker_{secrets.token_hex(4)}"


def _resolve_providers(db: Session):
    """Prefer app.services.orchestrator.resolve_providers so tests can monkeypatch."""
    from app.services import orchestrator as orch_mod

    fn = getattr(orch_mod, "resolve_providers", None)
    if callable(fn):
        return fn(db)
    from app.providers.registry import resolve_providers

    return resolve_providers(db)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _eid() -> str:
    return f"evt_{secrets.token_hex(8)}"


def _merge_sources(*groups: list[Source] | None) -> list[Source]:
    out: list[Source] = []
    seen: set[str] = set()
    for group in groups:
        for s in group or []:
            if s.url in seen:
                continue
            seen.add(s.url)
            out.append(s)
    return out


async def _emit(db: Session, run: Run, **kwargs) -> RunEventOut:
    # Map internal stage names to UI phases when needed
    phase = kwargs.get("phase") or run.phase
    phase = ui_phase(phase) if phase in {
        "memory_lookup",
        "research_plan",
        "market_research",
        "market_rank",
        "await_market_select",
        "buyer_research",
    } else phase
    kwargs["phase"] = phase

    event_id = kwargs.pop("event_id", None) or _eid()
    event, created = append_event(db, run_id=run.id, event_id=event_id, **kwargs)
    run.phase = phase
    status = kwargs["status"]
    if run.status != "cancelled":
        run.status = "running" if run.phase != "report" and status in {"completed", "partial"} else status
    run.updated_at = datetime.now(timezone.utc)
    if kwargs.get("error_code"):
        run.error_code = kwargs["error_code"]
        run.error_message_fa = kwargs.get("message_fa")
        run.error_retryable = (
            1
            if kwargs["error_code"]
            in {
                "PROVIDER_UNAVAILABLE",
                "RATE_LIMITED",
                "INSUFFICIENT_EVIDENCE",
                "BUDGET_EXCEEDED",
                "LLM_UNAVAILABLE",
                "LLM_INVALID",
                "LEASE_LOST",
                "MODEL_BILLING",
                "MODEL_RATE_LIMITED",
                "MODEL_UNAVAILABLE",
                "MODEL_FAILED",
            } or str(kwargs["error_code"]).startswith("OPERATIONAL_")
            else 0
        )
    db.commit()
    if created:
        await broadcaster.publish(run.id, event.model_dump())
    delay = get_settings().orchestrator_step_delay_ms / 1000.0
    if delay > 0:
        await asyncio.sleep(delay)
    return event


async def run_agentic_pipeline(run_id: str) -> None:
    db = SessionLocal()
    task = None
    try:
        recover_stale_leases(db)
        ensure_global_budget(db)
        run = db.get(Run, run_id)
        if not run:
            return

        task = latest_task_for_run(db, run_id)
        if task is None or task.status not in {"queued", "interrupted"}:
            task = create_task(
                db,
                run_id=run_id,
                stage="market_research",
                checkpoint={"version": 2, "completed_steps": []},
            )
        claimed = claim_task(db, task.id, _WORKER_ID)
        if not claimed:
            return
        try:
            checkpoint = json.loads(claimed.checkpoint_json or "{}")
        except json.JSONDecodeError:
            checkpoint = {}

        ensure_run_budget(db, run_id)
        bundle = _resolve_providers(db)
        executor = ToolExecutor(
            db,
            run_id=run_id,
            search=bundle.search,
            trade_service=bundle.trade_service,
            llm=bundle.llm,
        )

        await _emit(
            db,
            run,
            phase="intake",
            status="queued",
            message_fa="درخواست در صف اجرای ایجنت قرار گرفت",
            payload={"provider_mode": bundle.mode, "notes": bundle.notes_fa, "agentic": True},
        )
        await _emit(
            db,
            run,
            phase="intake",
            status="running",
            message_fa="شروع پردازش ایجنت‌محور",
        )
        await _emit(
            db,
            run,
            phase="intake",
            status="completed",
            message_fa="ورود درخواست تکمیل شد",
        )

        result = await run_market_research(
            db,
            run,
            executor,
            _emit,
            checkpoint=checkpoint,
            task_id=claimed.id,
            lease_owner=_WORKER_ID,
        )
        if result.get("stop_reason") == "LEASE_LOST":
            return
        markets = result.get("markets") or []
        sources = result.get("sources") or []
        recommended = result.get("recommended") or []
        risky = result.get("risky") or []
        data_scope = result.get("data_scope") or "sector"
        trade_meta = result.get("trade_meta") or {}
        provisional = bool(result.get("provisional"))
        stop = str(result.get("stop_reason") or "")
        quality = trade_meta.get("quality_status") or (
            "partial" if markets else "unavailable"
        )

        if not markets:
            notes = str((result.get("plan") or {}).get("notes_fa") or "")
            blocked = stop in {
                "LLM_UNAVAILABLE",
                "LLM_INVALID",
                "LEASE_LOST",
                "MODEL_BILLING",
                "MODEL_RATE_LIMITED",
                "MODEL_UNAVAILABLE",
                "MODEL_FAILED",
                "MARKET_DISCOVERY_INCOMPLETE",
                "BUYER_RESEARCH_BLOCKED",
                "NO_NEW_SOURCES",
            } or stop.startswith("OPERATIONAL_")
            await _emit(
                db,
                run,
                phase="conclude",
                status="partial",
                message_fa=notes or (
                    "پژوهش مسدود است و قابل بازیابی است"
                    if blocked
                    else "اطلاعات ناکافی برای پیشنهاد بازار"
                ),
                error_code=stop if blocked else "INSUFFICIENT_EVIDENCE",
                event_id=f"evt_{run.id}_conclude",
            )
            summary = notes or (
                "پژوهش بازار مسدود است و قابل بازیابی است. تصمیم اکتشافی اجرا نشد."
                if blocked
                else (
                    "در این اجرا شواهد کافی برای رتبه‌بندی بازار به‌دست نیامد "
                    f"(وضعیت داده: {quality}). عدد/شرکت ساختگی تولید نشد."
                )
            )
            report = Report(
                run_id=run.id,
                product=run.product,
                origin_country=run.origin_country,
                summary_fa=summary,
                markets=[],
                selected_country=None,
                buyers=[],
                risks_fa=["نبود داده تجاری کافی", "ارائه‌دهنده زنده ممکن است پیکربندی نشده باشد"],
                assumptions_fa=[
                    "بدون جعل آمار یا خریدار",
                    "محاسبه مالی فقط پس از ورود اعداد کاربر",
                    f"کیفیت داده تجارت: {quality}",
                    "تصمیم تحقیق فقط از مدل تأییدشده می‌آید؛ در نبود آن وضعیت مسدود است",
                ],
                sources=_merge_sources(sources),
                collected_at=_iso(datetime.now(timezone.utc)),
                is_mock=False,
            )
            run.report_json = report.model_dump_json()
            if run.status != "cancelled":
                run.status = "partial"
            run.phase = "report"
            run.error_code = stop if blocked else "INSUFFICIENT_EVIDENCE"
            run.error_message_fa = (notes or "پژوهش مسدود است") if blocked else "شواهد کافی نیست"
            run.error_retryable = 1
            await _emit(
                db,
                run,
                phase="report",
                status="partial",
                message_fa="گزارش ناقص آماده شد (بدون بازار رتبه‌بندی‌شده)",
            )
            finish_task(
                db,
                task.id,
                status="blocked" if blocked else "completed",
                error_code=run.error_code,
                error_message_fa=run.error_message_fa,
            )
            return

        await _emit(
            db,
            run,
            phase="conclude",
            status="partial" if provisional else "completed",
            message_fa=(
                f"رتبه‌بندی آماده — {len(recommended)} پیشنهاد، {len(risky)} پرریسک. "
                "برای تحقیق خریدار یک کشور را انتخاب کنید."
            ),
            payload={
                "event_type": "market.gate",
                "recommended": [m.country_code for m in recommended],
                "risky": [m.country_code for m in risky],
                "provisional": provisional,
                "awaiting": "select_country",
            },
        )

        src_name = trade_meta.get("source_name") or "TradeData/Agent"
        ref_year = trade_meta.get("reference_year")
        report = Report(
            run_id=run.id,
            product=run.product,
            origin_country=run.origin_country,
            summary_fa=(
                ("نتایج موقت پس از توقف عملیات. " if provisional else "")
                + f"تحلیل ایجنت‌محور برای «{run.product}» از {src_name}"
                + (f" (سال مرجع {ref_year})" if ref_year else "")
                + f". دامنه داده: {data_scope}. کیفیت: {quality}. "
                f"{len(recommended)} بازار پیشنهادی"
                + (f" و {len(risky)} بازار پرریسک." if risky else ".")
                + " انتخاب کشور برای مرحله خریداران الزامی است."
            ),
            markets=markets,
            buyers=[],
            risks_fa=[
                "داده گروهی/کل ممکن است با تقاضای محصول‌محور HS هم‌خوان نباشد"
                if data_scope in {"sector", "total"}
                else "ریسک تفسیر بیش‌ازحد آمار",
                "خریدار بالقوه هنوز جست‌وجو/تأیید نشده",
                *list(trade_meta.get("warnings") or [])[:2],
            ],
            assumptions_fa=[
                "مبدأ پیش‌فرض ایران مگر خلاف آن ثبت شود",
                "رتبه‌بندی قطعی روی معیارهای معلوم؛ معیارهای نامعلوم صفر جعلی نگرفتند",
                f"کیفیت داده تجارت: {quality}",
                f"HS: {run.guessed_hs_code or 'نامشخص'}",
                f"حافظه: {result.get('memory_status')}",
            ],
            sources=_merge_sources(sources, *[m.sources for m in markets]),
            collected_at=_iso(datetime.now(timezone.utc)),
            is_mock=False,
        )
        run.report_json = report.model_dump_json()
        # Buyer research remains gated on explicit country select (no auto-buyers).
        if run.status != "cancelled":
            run.status = "partial" if provisional else "completed"
        run.phase = "report"
        run.error_code = stop if provisional else None
        run.error_message_fa = (result.get("plan") or {}).get("notes_fa") if provisional else None
        run.error_retryable = int(provisional)
        await _emit(
            db,
            run,
            phase="report",
            status="partial" if provisional else "completed",
            message_fa="گزارش بازار آماده است — برای خریداران یک کشور را انتخاب کنید",
            payload={"event_type": "report.ready", "awaiting": "select_country"},
        )
        finish_task(
            db,
            task.id,
            status="blocked" if provisional else "completed",
            error_code=run.error_code,
            error_message_fa=run.error_message_fa,
        )
    except Exception:
        logging.getLogger(__name__).exception("Agentic pipeline failed for run %s", run_id)
        db.rollback()
        run = db.get(Run, run_id)
        if run is not None:
            await _emit(
                db,
                run,
                phase=run.phase,
                status="failed",
                message_fa="تحلیل به دلیل یک خطای داخلی متوقف شد.",
                error_code="PIPELINE_ERROR",
            )
        if task is not None:
            finish_task(
                db,
                task.id,
                status="failed",
                error_code="PIPELINE_ERROR",
                error_message_fa="خطای داخلی",
            )
    finally:
        db.close()


def schedule_agentic_pipeline(run_id: str) -> None:
    _pipeline_pool.submit(lambda: asyncio.run(run_agentic_pipeline(run_id)))
