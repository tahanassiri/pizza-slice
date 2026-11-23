from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.request_budget import enforce_request_budget
from app.core.run_access import grant_run_access, require_run_access
from app.db.session import SessionLocal, get_db
from app.events.broadcaster import sse_event_stream
from app.events.store import list_events
from app.models.entities import Run
from app.schemas.contracts import (
    CreateRunIn,
    CreateRunOut,
    Feasibility,
    FeasibilityIn,
    Market,
    Report,
    RunSnapshot,
    SelectCountryIn,
)
from app.services import runs as run_service

router = APIRouter(tags=["runs"])
access_required = [Depends(require_run_access)]


@router.post("/runs", response_model=CreateRunOut)
def create_run(body: CreateRunIn, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce_request_budget("analysis", get_settings().run_requests_per_hour)
    run_id = run_service.create_run(db, body)
    grant_run_access(run_id, request, response)
    return CreateRunOut(run_id=run_id)


@router.get("/runs/{run_id}", response_model=RunSnapshot, dependencies=access_required)
def get_run(run_id: str, db: Session = Depends(get_db)):
    return run_service.snapshot(db, run_id)


@router.get("/runs/{run_id}/markets", response_model=list[Market], dependencies=access_required)
def get_markets(run_id: str, db: Session = Depends(get_db)):
    return run_service.get_markets(db, run_id)


@router.post("/runs/{run_id}/buyers", response_model=RunSnapshot, dependencies=access_required)
def post_buyers(run_id: str, body: SelectCountryIn, db: Session = Depends(get_db)):
    enforce_request_budget("buyers", get_settings().buyer_requests_per_hour)
    return run_service.start_buyer_search(db, run_id, body.country_code)


@router.post("/runs/{run_id}/select-country", response_model=RunSnapshot, dependencies=access_required)
def select_country(run_id: str, body: SelectCountryIn, db: Session = Depends(get_db)):
    enforce_request_budget("buyers", get_settings().buyer_requests_per_hour)
    return run_service.select_country(db, run_id, body.country_code)


@router.post("/runs/{run_id}/feasibility", response_model=Feasibility, dependencies=access_required)
def post_feasibility(run_id: str, body: FeasibilityIn, db: Session = Depends(get_db)):
    return run_service.post_feasibility(
        db, run_id, body.cost_updates, input_assumptions=body.input_assumptions
    )


@router.get("/runs/{run_id}/report", response_model=Report, dependencies=access_required)
def get_report(run_id: str, db: Session = Depends(get_db)):
    return run_service.get_report(db, run_id)


@router.get("/runs/{run_id}/events", dependencies=access_required)
async def stream_events(
    run_id: str,
    request: Request,
    last_event_id: str | None = Query(default=None, alias="last_event_id"),
):
    def ensure_run_exists():
        with SessionLocal() as session:
            if session.get(Run, run_id) is None:
                raise AppError("RUN_NOT_FOUND", "اجرا یافت نشد.", 404)

    await run_in_threadpool(ensure_run_exists)
    # Prefer Last-Event-ID header for SSE resume
    header_id = request.headers.get("last-event-id")
    settings = get_settings()

    async def load_events(after: str | None):
        def read():
            with SessionLocal() as session:
                return [e.model_dump() for e in list_events(session, run_id, after_event_id=after)]

        return await run_in_threadpool(read)

    return EventSourceResponse(
        sse_event_stream(
            run_id=run_id,
            load_events=load_events,
            after_event_id=header_id or last_event_id,
            heartbeat_seconds=settings.sse_heartbeat_seconds,
        )
    )
