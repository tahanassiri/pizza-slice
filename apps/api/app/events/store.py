from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import RunEventRow
from app.schemas.contracts import RunEventOut, Source


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def row_to_event(row: RunEventRow) -> RunEventOut:
    payload = json.loads(row.payload_json) if row.payload_json else None
    refs = None
    if row.source_refs_json:
        refs = [Source.model_validate(x) for x in json.loads(row.source_refs_json)]
    return RunEventOut(
        event_id=row.event_id,
        run_id=row.run_id,
        phase=row.phase,
        status=row.status,
        message_fa=row.message_fa,
        timestamp=_iso(row.timestamp),
        payload=payload,
        source_refs=refs,
        error_code=row.error_code,
    )


def next_seq(db: Session, run_id: str) -> int:
    current = db.scalar(
        select(func.max(RunEventRow.seq)).where(RunEventRow.run_id == run_id)
    )
    return int(current or 0) + 1


def append_event(
    db: Session,
    *,
    run_id: str,
    event_id: str,
    phase: str,
    status: str,
    message_fa: str,
    payload: dict | None = None,
    source_refs: list[Source] | None = None,
    error_code: str | None = None,
) -> RunEventOut:
    seq = next_seq(db, run_id)
    row = RunEventRow(
        event_id=event_id,
        run_id=run_id,
        phase=phase,
        status=status,
        message_fa=message_fa,
        timestamp=datetime.now(timezone.utc),
        payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
        source_refs_json=(
            json.dumps([s.model_dump() for s in source_refs], ensure_ascii=False)
            if source_refs
            else None
        ),
        error_code=error_code,
        seq=seq,
    )
    db.add(row)
    db.flush()
    return row_to_event(row)


def list_events(
    db: Session, run_id: str, *, after_event_id: str | None = None
) -> list[RunEventOut]:
    q = select(RunEventRow).where(RunEventRow.run_id == run_id).order_by(RunEventRow.seq.asc())
    if after_event_id:
        cursor = select(RunEventRow.seq).where(
            RunEventRow.run_id == run_id, RunEventRow.event_id == after_event_id
        ).scalar_subquery()
        # Unknown cursors replay the full history for this run.
        q = q.where(RunEventRow.seq > func.coalesce(cursor, -1))
    return [row_to_event(r) for r in db.scalars(q)]


def get_event_seq(db: Session, event_id: str) -> int | None:
    row = db.scalar(select(RunEventRow).where(RunEventRow.event_id == event_id))
    return row.seq if row else None
