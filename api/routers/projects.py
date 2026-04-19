"""Project CRUD routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_active_user
from api.database import get_async_session
from api.deps import ensure_project_capacity, get_project_for_user
from api.models import Project, Run, Strategy, User
from api.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from core.data_feed import get_default_symbol


router = APIRouter(prefix="/api/projects", tags=["projects"])


async def _project_out(project: Project, db: AsyncSession) -> ProjectOut:
    strategy_count = await db.scalar(select(func.count(Strategy.id)).where(Strategy.project_id == project.id)) or 0
    last_run = await db.scalar(
        select(Run)
        .join(Strategy, Run.strategy_id == Strategy.id)
        .where(Strategy.project_id == project.id, Run.status == "complete")
        .order_by(Run.completed_at.desc())
        .limit(1)
    )
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        symbol=project.symbol,
        timeframe=None,
        created_at=project.created_at,
        updated_at=project.updated_at,
        strategy_count=strategy_count,
        last_run_sharpe=last_run.val_sharpe if last_run else None,
        last_run_date=last_run.completed_at if last_run else None,
    )


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> list[ProjectOut]:
    projects = (
        await db.scalars(
            select(Project).where(Project.user_id == user.id).order_by(Project.updated_at.desc())
        )
    ).all()
    return [await _project_out(project, db) for project in projects]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> ProjectOut:
    await ensure_project_capacity(user, db)
    project = Project(user_id=user.id, symbol=get_default_symbol(), **body.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return await _project_out(project, db)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> ProjectOut:
    project = await get_project_for_user(project_id, user, db)
    return await _project_out(project, db)


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> ProjectOut:
    project = await get_project_for_user(project_id, user, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return await _project_out(project, db)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> Response:
    project = await get_project_for_user(project_id, user, db)
    await db.delete(project)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
