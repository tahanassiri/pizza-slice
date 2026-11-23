from __future__ import annotations

import json
import re
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import SessionLocal
from app.events.store import list_events
from app.models.entities import BuyerSearchRow, Run
from app.schemas.contracts import (
    Buyer,
    BuyerSearchState,
    CostUpdate,
    CreateRunIn,
    Feasibility,
    FeasibilityAssumptions,
    Market,
    Report,
    RunError,
    RunOut,
    RunSnapshot,
    Source,
)
from app.providers.registry import resolve_providers
from app.services.feasibility_calc import default_feasibility_template, recompute
from app.services.orchestrator import schedule_pipeline


_buyer_lock = Lock()
_buyer_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="nova-buyers")
_active_buyer_statuses = ("queued", "running")


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def run_to_out(run: Run) -> RunOut:
    err = None
    if run.error_code:
        err = RunError(
            code=run.error_code,
            message_fa=run.error_message_fa or run.error_code,
            retryable=bool(run.error_retryable),
        )
    return RunOut(
        id=run.id,
        product=run.product,
        origin_country=run.origin_country,
        guessed_hs_code=run.guessed_hs_code,
        hs_confidence=run.hs_confidence,
        phase=run.phase,
        status=run.status,
        created_at=_iso(run.created_at),
        updated_at=_iso(run.updated_at),
        selected_country=run.selected_country,
        error=err,
        is_mock=bool(run.is_mock),
        fixture_id=None,
    )


def _load_json_list(raw: str | None, model):
    if not raw:
        return []
    return [model.model_validate(x) for x in json.loads(raw)]


def snapshot(db: Session, run_id: str) -> RunSnapshot:
    # A later run read can be ahead of the SSE cursor, but must never trail it.
    events = list_events(db, run_id)
    run = db.get(Run, run_id, populate_existing=True)
    if not run:
        raise AppError("RUN_NOT_FOUND", "اجرا یافت نشد.", 404)
    markets = _load_json_list(run.markets_json, Market)
    buyers = _load_json_list(run.buyers_json, Buyer)
    feasibility = Feasibility.model_validate_json(run.feasibility_json) if run.feasibility_json else None
    report = Report.model_validate_json(run.report_json) if run.report_json else None
    if report:
        feasibility = feasibility or report.feasibility or default_feasibility_template()
    if feasibility and any(not cost.required and cost.amount is None for cost in feasibility.cost_items):
        # Older runs could show totals while silently treating blank optional costs as zero.
        feasibility = recompute(feasibility)
    if report:
        report.feasibility = feasibility
    buyer_row = db.get(BuyerSearchRow, run_id, populate_existing=True)
    buyer_search = None
    if buyer_row and buyer_row.country_code == run.selected_country:
        buyers = _load_json_list(buyer_row.buyers_json, Buyer)
        buyer_search = BuyerSearchState(
            id=buyer_row.id,
            country_code=buyer_row.country_code,
            status=buyer_row.status,
            updated_at=_iso(buyer_row.updated_at),
            error=RunError(
                code=buyer_row.error_code,
                message_fa=buyer_row.error_message_fa or "خطا در جست‌وجوی خریدار.",
                retryable=True,
            ) if buyer_row.error_code else None,
        )
        if report:
            previous_buyer_urls = {source.url for item in report.buyers for source in item.sources}
            sources = {source.url: source for source in report.sources if source.url not in previous_buyer_urls}
            sources.update(
                (source.url, source) for source in _load_json_list(buyer_row.sources_json, Source)
            )
            report.selected_country = buyer_row.country_code
            report.buyers = buyers
            report.sources = list(sources.values())
    return RunSnapshot(
        run=run_to_out(run),
        last_event_id=events[-1].event_id if events else None,
        events=events,
        markets=markets,
        buyers=buyers,
        buyer_search=buyer_search,
        feasibility=feasibility,
        report=report,
    )


def create_run(db: Session, body: CreateRunIn) -> str:
    product = body.product.strip()
    if len(product) < 2:
        raise AppError("INVALID_PRODUCT", "نام محصول کوتاه است.")
    run_id = f"run_{secrets.token_hex(16)}"
    run = Run(
        id=run_id,
        product=product,
        origin_country=(body.origin_country or "ایران").strip() or "ایران",
        guessed_hs_code=body.hs_code.strip() if body.hs_code else None,
        hs_confidence="medium" if body.hs_code else "unknown",
        phase="intake",
        status="queued",
        is_mock=0,
        feasibility_json=default_feasibility_template().model_dump_json(),
    )
    db.add(run)
    db.commit()
    schedule_pipeline(run_id)
    return run_id


def get_markets(db: Session, run_id: str) -> list[Market]:
    return snapshot(db, run_id).markets


def start_buyer_search(db: Session, run_id: str, country_code: str) -> RunSnapshot:
    code = country_code.strip().upper()
    if re.fullmatch(r"[A-Z]{2}", code) is None:
        raise AppError("INVALID_COUNTRY", "کد کشور نامعتبر است.", 422)

    with _buyer_lock:
        run = db.get(Run, run_id)
        if not run:
            raise AppError("RUN_NOT_FOUND", "اجرا یافت نشد.", 404)
        choices = {market.country_code for market in _load_json_list(run.markets_json, Market)}
        if choices and code not in choices:
            raise AppError("INVALID_COUNTRY", "کشور در بازارهای این اجرا نیست.", 422)
        job = db.get(BuyerSearchRow, run_id)
        if job and job.country_code == code and job.status in _active_buyer_statuses:
            return snapshot(db, run_id)
        if not job:
            job = BuyerSearchRow(run_id=run_id)
            db.add(job)
        job_id = f"buy_{secrets.token_hex(12)}"
        job.id = job_id
        job.country_code = code
        job.status = "queued"
        job.updated_at = datetime.now(timezone.utc)
        job.buyers_json = job.sources_json = None
        job.error_code = job.error_message_fa = None
        run.selected_country = code
        run.buyers_json = None
        run.updated_at = job.updated_at
        db.commit()

    _buyer_pool.submit(_run_buyer_search, run_id, job_id)
    return snapshot(db, run_id)


def _run_buyer_search(run_id: str, job_id: str) -> None:
    with _buyer_lock, SessionLocal() as db:
        job = db.get(BuyerSearchRow, run_id)
        run = db.get(Run, run_id)
        if not job or job.id != job_id or not run:
            return
        product, country_code = run.product, job.country_code
        job.status = "running"
        job.updated_at = datetime.now(timezone.utc)
        db.commit()

    status = "failed"
    error_code = "PROVIDER_UNAVAILABLE"
    error_message = "جست‌وجوی خریدار انجام نشد. دوباره تلاش کنید."
    buyers = []
    sources = []
    try:
        with SessionLocal() as db:
            search = resolve_providers(db).search
        result = search.search_buyers(product, country_code)
        buyers = (result.buyers or [])[:10]
        sources = result.sources or []
        status = "completed" if buyers else "partial"
        error_code = None if buyers else result.error_code
        error_message = None if buyers else result.message_fa
    except Exception:
        pass

    with _buyer_lock, SessionLocal() as db:
        job = db.get(BuyerSearchRow, run_id)
        if not job or job.id != job_id:
            return
        job.status = status
        job.updated_at = datetime.now(timezone.utc)
        job.buyers_json = json.dumps([buyer.model_dump() for buyer in buyers], ensure_ascii=False)
        job.sources_json = json.dumps([source.model_dump() for source in sources], ensure_ascii=False)
        job.error_code = error_code
        job.error_message_fa = error_message
        db.commit()


def mark_interrupted_runs(db: Session) -> None:
    message = "پردازش با توقف سرویس قطع شد. دوباره تلاش کنید."
    db.execute(
        update(Run)
        .where(Run.report_json.is_(None), Run.status.in_(("queued", "running", "completed", "partial")))
        .values(status="failed", error_code="RUN_INTERRUPTED", error_message_fa=message, error_retryable=1)
    )
    db.execute(
        update(BuyerSearchRow)
        .where(BuyerSearchRow.status.in_(_active_buyer_statuses))
        .values(status="failed", error_code="RUN_INTERRUPTED", error_message_fa=message, updated_at=datetime.now(timezone.utc))
    )
    db.commit()


def select_country(db: Session, run_id: str, country_code: str) -> RunSnapshot:
    run = db.get(Run, run_id)
    if not run:
        raise AppError("RUN_NOT_FOUND", "اجرا یافت نشد.", 404)
    run.selected_country = country_code
    run.updated_at = datetime.now(timezone.utc)

    bundle = resolve_providers(db)
    result = bundle.search.search_buyers(run.product, country_code)
    buyers = result.buyers or []
    run.buyers_json = json.dumps([b.model_dump() for b in buyers], ensure_ascii=False)

    if run.report_json:
        report = Report.model_validate_json(run.report_json)
        report.selected_country = country_code
        report.buyers = buyers
        if result.sources:
            existing = {s.url for s in report.sources}
            report.sources = list(report.sources) + [
                s for s in result.sources if s.url not in existing
            ]
        run.report_json = report.model_dump_json()

    # Honest empty → surface as soft error; candidates clear prior buyer errors
    if not buyers and result.error_code:
        run.error_code = result.error_code
        run.error_message_fa = result.message_fa
        run.error_retryable = 1
    elif buyers:
        if run.error_code in {"NO_BUYERS", "INSUFFICIENT_EVIDENCE"}:
            run.error_code = None
            run.error_message_fa = None
            run.error_retryable = 0

    previous_job = db.get(BuyerSearchRow, run_id)
    if previous_job:
        db.delete(previous_job)
    db.commit()
    return snapshot(db, run_id)


def post_feasibility(
    db: Session,
    run_id: str,
    cost_updates: list[CostUpdate] | None,
    input_assumptions: FeasibilityAssumptions | None = None,
) -> Feasibility:
    for _ in range(3):
        run = db.get(Run, run_id)
        if not run:
            raise AppError("RUN_NOT_FOUND", "اجرا یافت نشد.", 404)
        previous = run.feasibility_json
        current = (
            Feasibility.model_validate_json(previous)
            if previous
            else default_feasibility_template()
        )
        if input_assumptions is not None:
            merged = current.input_assumptions | input_assumptions.model_dump(exclude_unset=True)
            current = current.model_copy(update={"input_assumptions": merged})
        next_f = recompute(current, cost_updates)
        # A concurrent edit may have saved different inputs since this read.
        saved = db.execute(
            update(Run)
            .where(Run.id == run_id, Run.feasibility_json == previous)
            .values(feasibility_json=next_f.model_dump_json(), updated_at=datetime.now(timezone.utc))
        )
        if saved.rowcount:
            db.commit()
            return next_f
        db.rollback()
    raise AppError("FEASIBILITY_CONFLICT", "ورودی‌ها هم‌زمان تغییر کردند. دوباره محاسبه کنید.", 409)


def get_report(db: Session, run_id: str) -> Report:
    snap = snapshot(db, run_id)
    if not snap.report:
        raise AppError("REPORT_UNAVAILABLE", "گزارش هنوز آماده نیست.", 404)
    return snap.report


def list_run_ids(db: Session) -> list[str]:
    return list(db.scalars(select(Run.id).order_by(Run.created_at.desc())).all())
