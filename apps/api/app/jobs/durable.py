"""Durable research task leases — survive process restart without silent 'running' forever."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.entities import ResearchTask

LEASE_SECONDS = 120


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_task(db: Session, *, run_id: str, stage: str, checkpoint: dict | None = None) -> ResearchTask:
    task = ResearchTask(
        id=f"task_{secrets.token_hex(10)}",
        run_id=run_id,
        stage=stage,
        status="queued",
        attempt=0,
        checkpoint_json=json.dumps(checkpoint or {}, ensure_ascii=False),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def claim_task(db: Session, task_id: str, owner: str) -> ResearchTask | None:
    now = _now()
    lease_until = now + timedelta(seconds=LEASE_SECONDS)
    result = db.execute(
        update(ResearchTask)
        .where(
            ResearchTask.id == task_id,
            ResearchTask.status.in_(("queued", "interrupted")),
        )
        .values(
            status="running",
            lease_owner=owner,
            lease_until=lease_until,
            attempt=ResearchTask.attempt + 1,
            updated_at=now,
        )
    )
    if result.rowcount == 0:
        # allow reclaim of expired lease
        result = db.execute(
            update(ResearchTask)
            .where(
                ResearchTask.id == task_id,
                ResearchTask.status == "running",
                ResearchTask.lease_until.is_not(None),
                ResearchTask.lease_until < now,
            )
            .values(
                lease_owner=owner,
                lease_until=lease_until,
                attempt=ResearchTask.attempt + 1,
                updated_at=now,
            )
        )
    db.commit()
    if result.rowcount == 0:
        return None
    return db.get(ResearchTask, task_id)


def finish_task(
    db: Session,
    task_id: str,
    *,
    status: str,
    checkpoint: dict | None = None,
    error_code: str | None = None,
    error_message_fa: str | None = None,
) -> None:
    task = db.get(ResearchTask, task_id)
    if not task:
        return
    task.status = status
    task.lease_owner = None
    task.lease_until = None
    task.updated_at = _now()
    if checkpoint is not None:
        task.checkpoint_json = json.dumps(checkpoint, ensure_ascii=False)
    task.error_code = error_code
    task.error_message_fa = error_message_fa
    db.commit()


def renew_lease(db: Session, task_id: str, owner: str) -> bool:
    now = _now()
    result = db.execute(
        update(ResearchTask)
        .where(
            ResearchTask.id == task_id,
            ResearchTask.status == "running",
            ResearchTask.lease_owner == owner,
        )
        .values(lease_until=now + timedelta(seconds=LEASE_SECONDS), updated_at=now)
    )
    db.commit()
    return int(result.rowcount or 0) > 0


def write_checkpoint(db: Session, task_id: str, checkpoint: dict) -> None:
    task = db.get(ResearchTask, task_id)
    if not task:
        return
    payload = dict(checkpoint)
    payload["version"] = int(payload.get("version") or 2)
    task.checkpoint_json = json.dumps(payload, ensure_ascii=False)
    task.updated_at = _now()
    db.commit()


def recover_stale_leases(db: Session) -> int:
    """Re-queue interrupted work. Expired lease alone is not proof of completion —
    tasks go to `interrupted` with checkpoint retained for safe retry (idempotent)."""
    now = _now()
    result = db.execute(
        update(ResearchTask)
        .where(
            ResearchTask.status == "running",
            ResearchTask.lease_until.is_not(None),
            ResearchTask.lease_until < now,
        )
        .values(
            status="interrupted",
            lease_owner=None,
            lease_until=None,
            error_code="LEASE_EXPIRED",
            error_message_fa=(
                "اجاره منقضی شد — تکمیل اثبات نشده؛ checkpoint نگه داشته شد برای تلاش امن مجدد."
            ),
            updated_at=now,
        )
    )
    # Also re-queue interrupted → queued so workers can claim again
    db.execute(
        update(ResearchTask)
        .where(ResearchTask.status == "interrupted")
        .values(status="queued", updated_at=now)
    )
    db.commit()
    return int(result.rowcount or 0)


def recover_on_startup(db: Session) -> list[str]:
    """Requeue work left by a dead process. Do not mark those runs failed.

    Called only when this process is starting and holds no leases. A queued
    status afterwards is not completion — callers must resume the checkpoint.
    """

    from app.models.entities import BuyerSearchRow, Run

    now = _now()
    resume: list[str] = []
    running = list(db.scalars(select(ResearchTask).where(ResearchTask.status == "running")).all())
    for task in running:
        task.status = "queued"
        task.lease_owner = None
        task.lease_until = None
        task.error_code = "PROCESS_RESTART"
        task.error_message_fa = "فرآیند قبلی قطع شد. checkpoint حفظ شد و کار دوباره در صف قرار گرفت."
        task.updated_at = now
        resume.append(task.run_id)
    interrupted = list(
        db.scalars(select(ResearchTask).where(ResearchTask.status == "interrupted")).all()
    )
    for task in interrupted:
        task.status = "queued"
        task.updated_at = now
        resume.append(task.run_id)
    open_runs = list(
        db.scalars(
            select(Run).where(
                Run.report_json.is_(None),
                Run.status.in_(("queued", "running", "interrupted")),
            )
        ).all()
    )
    for run in open_runs:
        run.status = "interrupted"
        run.error_code = "RUN_INTERRUPTED"
        run.error_message_fa = "اجرا پس از راه‌اندازی مجدد قابل ادامه است. شکست قطعی ثبت نشد."
        run.error_retryable = 1
        run.updated_at = now
        existing = latest_task_for_run(db, run.id)
        if existing is None or existing.status in {"failed", "completed"}:
            create_task(
                db,
                run_id=run.id,
                stage="market_research",
                checkpoint={"version": 2, "completed_steps": []},
            )
        resume.append(run.id)
    buyers = list(
        db.scalars(
            select(BuyerSearchRow).where(BuyerSearchRow.status.in_(("queued", "running")))
        ).all()
    )
    for job in buyers:
        if job.status == "running":
            job.status = "queued"
            job.error_code = None
            job.error_message_fa = "جست‌وجوی خریدار پس از راه‌اندازی مجدد در صف ادامه قرار گرفت."
            job.updated_at = now
    db.commit()
    return list(dict.fromkeys(resume))


def latest_task_for_run(db: Session, run_id: str) -> ResearchTask | None:
    return db.scalar(
        select(ResearchTask)
        .where(ResearchTask.run_id == run_id)
        .order_by(ResearchTask.created_at.desc())
        .limit(1)
    )
