"""Backtest run routes and metrics lookup."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_active_user
from api.database import get_async_session
from api.deps import ensure_run_capacity, get_run_for_user, get_strategy_for_user
from api.models import Project, Run, User
from api.runner import enqueue_run, load_run_artifact
from api.schemas import MetricsOut, RunOut, RunTriggerRequest


router = APIRouter(tags=["runs"])


@router.get("/api/strategies/{strategy_id}/runs", response_model=list[RunOut])
async def list_runs(
    strategy_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> list[Run]:
    await get_strategy_for_user(strategy_id, user, db)
    return (
        await db.scalars(
            select(Run).where(Run.strategy_id == strategy_id).order_by(Run.created_at.desc())
        )
    ).all()


@router.post("/api/strategies/{strategy_id}/runs/trigger", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_run(
    strategy_id: UUID,
    body: RunTriggerRequest,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> Run:
    strategy = await get_strategy_for_user(strategy_id, user, db)
    await ensure_run_capacity(user, db)
    project = await db.scalar(select(Project).where(Project.id == strategy.project_id))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return await enqueue_run(strategy, project, db, body.window_override, body.symbol_override)


@router.get("/api/runs/{run_id}", response_model=RunOut)
async def get_run(
    run_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> Run:
    return await get_run_for_user(run_id, user, db)


@router.get("/api/runs/{run_id}/metrics", response_model=MetricsOut)
async def get_run_metrics(
    run_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> MetricsOut:
    run = await get_run_for_user(run_id, user, db)
    if run.status != "complete":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Run is not complete yet.")

    run_data = load_run_artifact(run.result_path)
    return MetricsOut(
        train=run_data.get("train", {}).get("metrics", {}),
        validation=run_data.get("validation", {}).get("metrics", {}),
    )
