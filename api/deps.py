"""Shared FastAPI dependencies for auth, ownership, and quotas."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_active_user
from api.config import settings
from api.database import get_async_session
from api.models import Project, Run, Strategy, User


def project_limit_for_tier(tier: str) -> int | None:
    if tier == "elite":
        return None
    if tier == "pro":
        return settings.pro_max_projects
    return settings.free_max_projects


def strategy_limit_for_tier(tier: str) -> int | None:
    if tier == "elite":
        return None
    if tier == "pro":
        return settings.pro_max_strategies
    return settings.free_max_strategies


def run_limit_for_tier(tier: str) -> int | None:
    if tier == "elite":
        return None
    if tier == "pro":
        return settings.pro_max_runs_per_month
    return settings.free_max_runs_per_month


def require_tier(*allowed: str):
    allowed_tiers = set(allowed)

    async def dependency(user: User = Depends(current_active_user)) -> User:
        if user.tier not in allowed_tiers:
            allowed_list = ", ".join(sorted(allowed_tiers))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Upgrade required. Allowed tiers: {allowed_list}.",
            )
        return user

    return dependency


async def ensure_project_capacity(user: User, db: AsyncSession) -> None:
    limit = project_limit_for_tier(user.tier)
    if limit is None:
        return
    total = await db.scalar(select(func.count(Project.id)).where(Project.user_id == user.id))
    if (total or 0) >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Project limit reached for the {user.tier} tier.",
        )


async def ensure_strategy_capacity(user: User, project_id: UUID, db: AsyncSession) -> None:
    limit = strategy_limit_for_tier(user.tier)
    if limit is None:
        return
    total = await db.scalar(select(func.count(Strategy.id)).where(Strategy.project_id == project_id))
    if (total or 0) >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Strategy limit reached for the {user.tier} tier.",
        )


async def ensure_run_capacity(user: User, db: AsyncSession) -> None:
    limit = run_limit_for_tier(user.tier)
    if limit is None:
        return

    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = await db.scalar(
        select(func.count(Run.id))
        .join(Strategy, Run.strategy_id == Strategy.id)
        .join(Project, Strategy.project_id == Project.id)
        .where(Project.user_id == user.id, Run.created_at >= month_start)
    )
    if (total or 0) >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Monthly run limit reached for the {user.tier} tier.",
        )


async def get_project_for_user(project_id: UUID, user: User, db: AsyncSession) -> Project:
    project = await db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


async def get_strategy_for_user(strategy_id: UUID, user: User, db: AsyncSession) -> Strategy:
    strategy = await db.scalar(
        select(Strategy)
        .join(Project, Strategy.project_id == Project.id)
        .where(Strategy.id == strategy_id, Project.user_id == user.id)
    )
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found.")
    return strategy


async def get_run_for_user(run_id: UUID, user: User, db: AsyncSession) -> Run:
    run = await db.scalar(
        select(Run)
        .join(Strategy, Run.strategy_id == Strategy.id)
        .join(Project, Strategy.project_id == Project.id)
        .where(Run.id == run_id, Project.user_id == user.id)
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return run
