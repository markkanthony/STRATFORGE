"""Chart data endpoint for OHLCV, trades, and equity curves."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_active_user
from api.database import get_async_session
from api.deps import get_run_for_user
from api.models import User
from api.runner import load_run_artifact, to_unix_timestamp
from api.schemas import ChartDataResponse, ChartTrade, EquityPoint, OhlcvPoint


router = APIRouter(tags=["chart"])


@router.get("/api/runs/{run_id}/chart-data", response_model=ChartDataResponse)
async def get_chart_data(
    run_id: UUID,
    window: str = Query("validation", pattern="^(train|validation)$"),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> ChartDataResponse:
    run = await get_run_for_user(run_id, user, db)
    if run.status != "complete":
        raise HTTPException(status_code=409, detail="Run is not complete yet.")

    run_data = load_run_artifact(run.result_path)
    config_snapshot = run_data.get("config_snapshot", {})
    window_meta = run_data.get("windows", {}).get(window, {})
    symbol = run_data.get("symbol") or config_snapshot.get("backtest", {}).get("symbol", "EURUSD")
    timeframe = run_data.get("timeframe") or config_snapshot.get("backtest", {}).get("timeframe", "H1")

    try:
        from core.data_feed import get_ohlcv

        ohlcv_df = get_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            start_date=str(window_meta.get("start", "")),
            end_date=str(window_meta.get("end", "")),
            config=config_snapshot,
        )
        ohlcv = [
            OhlcvPoint(
                time=to_unix_timestamp(row["time"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row.get("tick_volume", 0)),
            )
            for _, row in ohlcv_df.iterrows()
        ]
    except Exception:
        ohlcv = []

    raw_trades = run_data.get(window, {}).get("trades", [])
    trades = [
        ChartTrade(
            trade_idx=index,
            entry_time=to_unix_timestamp(trade["entry_time"]),
            exit_time=to_unix_timestamp(trade["exit_time"]),
            entry_price=float(trade["entry_price"]),
            exit_price=float(trade["exit_price"]),
            sl_price=trade.get("sl_price"),
            tp_price=trade.get("tp_price"),
            side=trade["side"],
            exit_reason=trade.get("exit_reason", ""),
            pnl=float(trade.get("pnl", 0)),
            r_multiple=trade.get("r_multiple"),
            bars_held=trade.get("bars_held"),
            session=trade.get("entry_session"),
        )
        for index, trade in enumerate(raw_trades)
    ]

    raw_equity = run_data.get(window, {}).get("equity_curve", [])
    equity = [
        EquityPoint(time=to_unix_timestamp(point["time"]), value=float(point["equity"]))
        for point in raw_equity
    ]

    return ChartDataResponse(
        ohlcv=ohlcv,
        trades=trades,
        equity=equity,
        symbol=symbol,
        timeframe=timeframe,
        window=window,
    )
