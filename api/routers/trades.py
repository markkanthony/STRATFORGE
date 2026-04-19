"""Trades endpoint split from chart data for paginated tables."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_active_user
from api.database import get_async_session
from api.deps import get_run_for_user
from api.models import User
from api.runner import load_run_artifact, to_unix_timestamp
from api.schemas import TradeOut, TradesResponse


router = APIRouter(tags=["trades"])


@router.get("/api/runs/{run_id}/trades", response_model=TradesResponse)
async def get_trades(
    run_id: UUID,
    window: str = Query("validation", pattern="^(train|validation)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> TradesResponse:
    run = await get_run_for_user(run_id, user, db)
    if run.status != "complete":
        raise HTTPException(status_code=409, detail="Run is not complete yet.")

    run_data = load_run_artifact(run.result_path)
    raw_trades = run_data.get(window, {}).get("trades", [])

    total = len(raw_trades)
    start = (page - 1) * page_size
    sliced = raw_trades[start : start + page_size]
    trades = [
        TradeOut(
            trade_idx=start + index,
            side=trade["side"],
            entry_time=to_unix_timestamp(trade["entry_time"]),
            exit_time=to_unix_timestamp(trade["exit_time"]),
            entry_price=float(trade["entry_price"]),
            exit_price=float(trade["exit_price"]),
            sl_price=trade.get("sl_price"),
            tp_price=trade.get("tp_price"),
            size=trade.get("size"),
            pnl=float(trade.get("pnl", 0)),
            pnl_pct=trade.get("pnl_pct"),
            r_multiple=trade.get("r_multiple"),
            bars_held=trade.get("bars_held"),
            session=trade.get("entry_session"),
            exit_reason=trade.get("exit_reason", ""),
        )
        for index, trade in enumerate(sliced)
    ]
    return TradesResponse(total=total, page=page, page_size=page_size, trades=trades)
