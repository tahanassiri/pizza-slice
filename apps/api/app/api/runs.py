from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core.config import get_settings
from app.db.session import get_db
from app.events.broadcaster import sse_event_stream
from app.events.store import list_events
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


@router.post("/runs", response_model=CreateRunOut)
def create_run(body: CreateRunIn, db: Session = Depends(get_db)):
    run_id = run_service.create_run(db, body)
    return CreateRunOut(run_id=run_id)


@router.get("/runs/{run_id}", response_model=RunSnapshot)
def get_run(run_id: str, db: Session = Depends(get_db)):
    return run_service.snapshot(db, run_id)


@router.get("/runs/{run_id}/markets", response_model=list[Market])
def get_markets(run_id: str, db: Session = Depends(get_db)):
    return run_service.get_markets(db, run_id)


@router.post("/runs/{run_id}/buyers", response_model=RunSnapshot)
def post_buyers(run_id: str, body: SelectCountryIn, db: Session = Depends(get_db)):
    # Country selection triggers buyer discovery task (stub in Phase B)
    return run_service.select_country(db, run_id, body.country_code)


@router.post("/runs/{run_id}/select-country", response_model=RunSnapshot)
def select_country(run_id: str, body: SelectCountryIn, db: Session = Depends(get_db)):
    return run_service.select_country(db, run_id, body.country_code)


@router.post("/runs/{run_id}/feasibility", response_model=Feasibility)
def post_feasibility(run_id: str, body: FeasibilityIn, db: Session = Depends(get_db)):
    return run_service.post_feasibility(
        db, run_id, body.cost_updates, input_assumptions=body.input_assumptions
    )


@router.get("/runs/{run_id}/report", response_model=Report)
def get_report(run_id: str, db: Session = Depends(get_db)):
    return run_service.get_report(db, run_id)


@router.get("/runs/{run_id}/events")
async def stream_events(
    run_id: str,
    request: Request,
    last_event_id: str | None = Query(default=None, alias="last_event_id"),
    db: Session = Depends(get_db),
):
    # Validate run exists
    run_service.snapshot(db, run_id)
    # Prefer Last-Event-ID header for SSE resume
    header_id = request.headers.get("last-event-id")
    after = last_event_id or header_id
    initial = [e.model_dump() for e in list_events(db, run_id, after_event_id=after)]
    settings = get_settings()

    async def gen():
        async for item in sse_event_stream(
            run_id=run_id,
            initial_events=initial,
            heartbeat_seconds=settings.sse_heartbeat_seconds,
        ):
            if await request.is_disconnected():
                break
            yield item

    # ping=0 disables sse-starlette's built-in ping; we emit explicit heartbeats
    return EventSourceResponse(gen(), ping=0)
