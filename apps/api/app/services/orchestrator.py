from __future__ import annotations

import asyncio
import json
import logging
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.events.broadcaster import broadcaster
from app.events.store import append_event
from app.models.entities import Run
from app.providers.registry import resolve_providers
from app.schemas.contracts import Report, RunEventOut, Source
from app.trade_data.adapter import TradeDataProviderAdapter


_pipeline_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="nova-pipeline")


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _eid() -> str:
    return f"evt_{secrets.token_hex(8)}"


async def _emit(db: Session, run: Run, **kwargs) -> RunEventOut:
    event = append_event(db, run_id=run.id, event_id=_eid(), **kwargs)
    run.phase = kwargs["phase"]
    run.status = kwargs["status"]
    run.updated_at = datetime.now(timezone.utc)
    if kwargs.get("error_code"):
        run.error_code = kwargs["error_code"]
        run.error_message_fa = kwargs.get("message_fa")
        run.error_retryable = (
            1
            if kwargs["error_code"]
            in {"PROVIDER_UNAVAILABLE", "RATE_LIMITED", "INSUFFICIENT_EVIDENCE"}
            else 0
        )
    db.commit()
    await broadcaster.publish(run.id, event.model_dump())
    delay = get_settings().orchestrator_step_delay_ms / 1000.0
    if delay > 0:
        await asyncio.sleep(delay)
    return event


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


async def run_pipeline(run_id: str) -> None:
    """Background orchestration — real stage events; free/keyed providers via registry."""
    db = SessionLocal()
    try:
        run = db.get(Run, run_id)
        if not run:
            return

        bundle = resolve_providers(db)
        llm = bundle.llm
        search = bundle.search
        trade = bundle.trade

        await _emit(
            db,
            run,
            phase="intake",
            status="queued",
            message_fa="درخواست در صف اجرا قرار گرفت",
            payload={"provider_mode": bundle.mode, "notes": bundle.notes_fa},
        )
        await _emit(
            db,
            run,
            phase="intake",
            status="running",
            message_fa="شروع پردازش درخواست",
        )
        await _emit(
            db,
            run,
            phase="intake",
            status="completed",
            message_fa="ورود درخواست تکمیل شد",
        )

        hs, hs_conf = llm.classify_hs(run.product, run.guessed_hs_code)
        run.guessed_hs_code = hs
        run.hs_confidence = hs_conf
        db.commit()

        await _emit(
            db,
            run,
            phase="product_classify",
            status="running",
            message_fa=(
                f"طبقه‌بندی محصول: HS قطعی ثبت نشد (اطمینان {hs_conf})"
                if not hs
                else f"کد HS پیشنهادی کاربر/سیستم: {hs} (اطمینان {hs_conf})"
            ),
            payload={"guessed_hs_code": hs, "hs_confidence": hs_conf},
        )
        await _emit(
            db,
            run,
            phase="product_classify",
            status="completed",
            message_fa="مرحله طبقه‌بندی تمام شد",
        )

        await _emit(
            db,
            run,
            phase="trade_stats",
            status="running",
            message_fa="بازیابی داده تجارت (WITS → تحقیق → منابع اختیاری)",
        )

        extra_sources: list[Source] = []
        # TradeDataService path — market modules never call Comtrade/WITS directly
        if isinstance(trade, TradeDataProviderAdapter):
            trade_result, market_result = trade.trade_stats_and_markets(
                run.product, run.origin_country, hs_code=run.guessed_hs_code
            )
        else:
            trade_result = trade.trade_stats(run.product, run.origin_country)
            if hasattr(trade, "build_markets"):
                market_result = trade.build_markets(run.product, run.origin_country)
            else:
                market_result = search.search_markets(run.product, run.origin_country)

        await _emit(
            db,
            run,
            phase="trade_stats",
            status="completed" if trade_result.ok else "partial",
            message_fa=trade_result.message_fa,
            source_refs=trade_result.sources,
            error_code=None if trade_result.ok else trade_result.error_code,
            payload={
                "quality_status": (trade_result.meta or {}).get("quality_status"),
                "cache_hit": (trade_result.meta or {}).get("cache_hit"),
                "warnings": (trade_result.meta or {}).get("warnings"),
            },
        )

        await _emit(
            db,
            run,
            phase="search",
            status="running",
            message_fa="تحقیق تکمیلی و اعتبارسنجی منابع",
        )
        if hasattr(search, "search_product_context"):
            try:
                ctx = search.search_product_context(run.product)
                extra_sources = list(ctx.sources or [])
            except Exception:
                pass
        elif hasattr(search, "search_markets"):
            try:
                supp = search.search_markets(run.product, run.origin_country)
                extra_sources = list(supp.sources or [])
            except Exception:
                pass

        await _emit(
            db,
            run,
            phase="search",
            status="completed" if market_result.ok or extra_sources else "partial",
            message_fa=market_result.message_fa
            if market_result.ok
            else (market_result.message_fa or "تحقیق تکمیلی بدون عدد قطعی"),
            source_refs=_merge_sources(market_result.sources, extra_sources),
            error_code=None if market_result.ok else market_result.error_code,
            payload={
                "markets_found": len(market_result.markets or []),
                "quality_status": (market_result.meta or {}).get("quality_status"),
            },
        )

        await _emit(
            db,
            run,
            phase="market_compare",
            status="running",
            message_fa="تحلیل و مقایسه بازارهای کاندید",
        )

        markets = market_result.markets or []
        run.markets_json = json.dumps(
            [m.model_dump() for m in markets], ensure_ascii=False
        )
        db.commit()

        all_sources = _merge_sources(
            market_result.sources, trade_result.sources, extra_sources
        )
        quality = (market_result.meta or {}).get("quality_status") or (
            trade_result.meta or {}
        ).get("quality_status")

        await _emit(
            db,
            run,
            phase="market_compare",
            status="completed" if markets else "partial",
            message_fa=(
                f"مقایسه بازار تمام شد — {len(markets)} کشور کاندید"
                if markets
                else "مقایسه بازار بدون کاندید قطعی (داده ناقص)"
            ),
            source_refs=market_result.sources,
            error_code=None
            if markets
            else (market_result.error_code or "INSUFFICIENT_EVIDENCE"),
            payload={
                "markets_found": len(markets),
                "quality_status": quality,
                "country_codes": [m.country_code for m in markets],
            },
        )

        if not markets:
            await _emit(
                db,
                run,
                phase="conclude",
                status="partial",
                message_fa="اطلاعات ناکافی برای پیشنهاد بازار",
                error_code=market_result.error_code or "INSUFFICIENT_EVIDENCE",
            )
            report = Report(
                run_id=run.id,
                product=run.product,
                origin_country=run.origin_country,
                summary_fa=(
                    "در این اجرا شواهد کافی برای رتبه‌بندی بازار به‌دست نیامد "
                    f"(وضعیت داده: {quality or 'unavailable'}). "
                    "خریدار و امکان‌سنجی همچنان در دسترس‌اند؛ عدد ساختگی تولید نشد."
                ),
                markets=[],
                selected_country=None,
                buyers=[],
                risks_fa=[
                    "نبود داده تجاری کافی",
                    "Comtrade کلید اجباری نیست — در صورت نیاز فقط به‌صورت اختیاری فعال شود",
                ],
                assumptions_fa=[
                    "بدون جعل آمار یا خریدار",
                    "محاسبه مالی فقط پس از ورود اعداد کاربر",
                    f"کیفیت داده تجارت: {quality or 'unavailable'}",
                ],
                sources=all_sources,
                collected_at=_iso(datetime.now(timezone.utc)),
                is_mock=False,
            )
            run.report_json = report.model_dump_json()
            run.status = "partial"
            run.phase = "report"
            run.error_code = market_result.error_code or "INSUFFICIENT_EVIDENCE"
            run.error_message_fa = market_result.message_fa
            run.error_retryable = 1
            db.commit()
            await _emit(
                db,
                run,
                phase="report",
                status="partial",
                message_fa="گزارش ناقص آماده شد (بدون بازار رتبه‌بندی‌شده)",
            )
            return

        await _emit(
            db,
            run,
            phase="conclude",
            status="completed",
            message_fa="رتبه‌بندی بازارها آماده شد (حداکثر ۳)",
        )
        src_name = (market_result.meta or {}).get("source_name") or "TradeData"
        ref_year = (market_result.meta or {}).get("reference_year")
        report = Report(
            run_id=run.id,
            product=run.product,
            origin_country=run.origin_country,
            summary_fa=(
                f"حداکثر سه بازار کاندید برای «{run.product}» از {src_name}"
                + (f" (سال مرجع {ref_year})" if ref_year else "")
                + f". کیفیت داده: {quality or 'partial'}."
            ),
            markets=markets,
            buyers=[],
            risks_fa=[
                "داده گروهی/کل ممکن است با تقاضای محصول‌محور HS هم‌خوان نباشد",
                "خریدار بالقوه هنوز جست‌وجو/تأیید نشده",
                *list((market_result.meta or {}).get("warnings") or [])[:2],
            ],
            assumptions_fa=[
                "مبدأ پیش‌فرض ایران مگر خلاف آن ثبت شود",
                "مسیر داده: WITS → تحقیق موجود → Comtrade اختیاری (بدون کلید اجباری)",
                f"کیفیت داده تجارت: {quality or 'partial'}",
                f"HS: {run.guessed_hs_code or 'نامشخص'}",
            ],
            sources=all_sources,
            collected_at=_iso(datetime.now(timezone.utc)),
            is_mock=False,
        )
        run.report_json = report.model_dump_json()
        run.status = "completed"
        run.phase = "report"
        run.error_code = None
        run.error_message_fa = None
        db.commit()
        await _emit(
            db,
            run,
            phase="report",
            status="completed",
            message_fa="گزارش آماده است",
        )
    except Exception:
        logging.getLogger(__name__).exception("Pipeline failed for run %s", run_id)
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
    finally:
        db.close()


def schedule_pipeline(run_id: str) -> None:
    _pipeline_pool.submit(lambda: asyncio.run(run_pipeline(run_id)))
