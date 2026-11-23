from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.events.store import list_events
from app.models.entities import Run
from app.schemas.contracts import (
    Buyer,
    CreateRunIn,
    Feasibility,
    Market,
    Report,
    RunError,
    RunOut,
    RunSnapshot,
)
from app.providers.registry import resolve_providers
from app.services.feasibility_calc import default_feasibility_template, recompute
from app.services.orchestrator import schedule_pipeline


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
    run = db.get(Run, run_id)
    if not run:
        raise AppError("RUN_NOT_FOUND", "اجرا یافت نشد.", 404)
    events = list_events(db, run_id)
    markets = _load_json_list(run.markets_json, Market)
    buyers = _load_json_list(run.buyers_json, Buyer)
    feasibility = Feasibility.model_validate_json(run.feasibility_json) if run.feasibility_json else None
    report = Report.model_validate_json(run.report_json) if run.report_json else None
    return RunSnapshot(
        run=run_to_out(run),
        last_event_id=events[-1].event_id if events else None,
        events=events,
        markets=markets,
        buyers=buyers,
        feasibility=feasibility,
        report=report,
    )


def create_run(db: Session, body: CreateRunIn) -> str:
    product = body.product.strip()
    if len(product) < 2:
        raise AppError("INVALID_PRODUCT", "نام محصول کوتاه است.")
    run_id = f"run_{secrets.token_hex(6)}"
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

    # Emit buyer stage status into run error fields when honest empty
    if not buyers and result.error_code:
        run.error_code = result.error_code
        run.error_message_fa = result.message_fa
        run.error_retryable = 1

    db.commit()
    return snapshot(db, run_id)


def post_feasibility(
    db: Session,
    run_id: str,
    cost_updates,
    input_assumptions: dict | None = None,
) -> Feasibility:
    run = db.get(Run, run_id)
    if not run:
        raise AppError("RUN_NOT_FOUND", "اجرا یافت نشد.", 404)
    current = (
        Feasibility.model_validate_json(run.feasibility_json)
        if run.feasibility_json
        else default_feasibility_template()
    )
    if input_assumptions:
        merged = dict(current.input_assumptions)
        merged.update(input_assumptions)
        current = current.model_copy(update={"input_assumptions": merged})
    next_f = recompute(current, cost_updates)
    run.feasibility_json = next_f.model_dump_json()
    if run.report_json:
        report = Report.model_validate_json(run.report_json)
        report.feasibility = next_f
        run.report_json = report.model_dump_json()
    run.updated_at = datetime.now(timezone.utc)
    db.commit()
    return next_f


def get_report(db: Session, run_id: str) -> Report:
    snap = snapshot(db, run_id)
    if not snap.report:
        raise AppError("REPORT_UNAVAILABLE", "گزارش هنوز آماده نیست.", 404)
    return snap.report


def list_run_ids(db: Session) -> list[str]:
    return list(db.scalars(select(Run.id).order_by(Run.created_at.desc())).all())
