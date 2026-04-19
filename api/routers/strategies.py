"""Strategy CRUD routes."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_active_user
from api.database import get_async_session
from api.deps import ensure_strategy_capacity, get_project_for_user, get_strategy_for_user
from api.models import Strategy, User
from api.runner import load_base_config, normalize_strategy_config
from api.schemas import StrategyCreate, StrategyOut, StrategyUpdate
from strategy import build_default_python_strategy_config, validate_entry_code_source


router = APIRouter(tags=["strategies"])


def _default_strategy_payload() -> dict:
    return build_default_python_strategy_config(load_base_config())


def _validate_strategy_payload(payload: dict) -> dict:
    normalized = build_default_python_strategy_config(normalize_strategy_config(payload))
    entry_code = normalized.get("strategy", {}).get("entry_code")
    if not isinstance(entry_code, str) or not entry_code.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Strategy config must include strategy.entry_code.")
    try:
        validate_entry_code_source(entry_code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return normalized


def _strategy_out(strategy: Strategy) -> StrategyOut:
    return StrategyOut(
        id=strategy.id,
        project_id=strategy.project_id,
        name=strategy.name,
        type=strategy.type,
        config_json=normalize_strategy_config(strategy.config_json),
        is_active=strategy.is_active,
        created_at=strategy.created_at,
        updated_at=strategy.updated_at,
    )


@router.get("/api/projects/{project_id}/strategies", response_model=list[StrategyOut])
async def list_strategies(
    project_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> list[StrategyOut]:
    await get_project_for_user(project_id, user, db)
    strategies = (
        await db.scalars(
            select(Strategy).where(Strategy.project_id == project_id).order_by(Strategy.updated_at.desc())
        )
    ).all()
    return [_strategy_out(strategy) for strategy in strategies]


@router.post("/api/projects/{project_id}/strategies", response_model=StrategyOut, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    project_id: UUID,
    body: StrategyCreate,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> StrategyOut:
    await get_project_for_user(project_id, user, db)
    await ensure_strategy_capacity(user, project_id, db)
    config_payload = _validate_strategy_payload(body.config_json or _default_strategy_payload())
    strategy = Strategy(
        project_id=project_id,
        name=body.name,
        type=body.type,
        config_json=json.dumps(config_payload),
        is_active=body.is_active,
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    return _strategy_out(strategy)


@router.get("/api/strategies/{strategy_id}", response_model=StrategyOut)
async def get_strategy(
    strategy_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> StrategyOut:
    strategy = await get_strategy_for_user(strategy_id, user, db)
    return _strategy_out(strategy)


@router.put("/api/strategies/{strategy_id}", response_model=StrategyOut)
async def update_strategy(
    strategy_id: UUID,
    body: StrategyUpdate,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> StrategyOut:
    strategy = await get_strategy_for_user(strategy_id, user, db)
    updates = body.model_dump(exclude_none=True)
    if "config_json" in updates:
        strategy.config_json = json.dumps(_validate_strategy_payload(updates.pop("config_json")))
    for field, value in updates.items():
        setattr(strategy, field, value)
    await db.commit()
    await db.refresh(strategy)
    return _strategy_out(strategy)


@router.delete("/api/strategies/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    strategy_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> Response:
    strategy = await get_strategy_for_user(strategy_id, user, db)
    await db.delete(strategy)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
