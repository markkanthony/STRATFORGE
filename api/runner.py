"""Async runner that wraps the existing `run.py` engine in a thread pool."""

from __future__ import annotations

import asyncio
import copy
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import ROOT_DIR, settings
from api.database import async_session_maker
from api.models import Project, Run, Strategy


if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="stratforge-run")
_config_lock = threading.Lock()


def load_base_config() -> dict[str, Any]:
    config_path = ROOT_DIR / settings.config_template_path
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def load_run_artifact(result_path: str | None) -> dict[str, Any]:
    if not result_path:
        raise FileNotFoundError("Run has no result artifact.")
    path = Path(result_path)
    if not path.is_absolute():
        path = ROOT_DIR / path
    if not path.exists():
        raise FileNotFoundError(f"Result file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def to_unix_timestamp(value: Any) -> int:
    return int(pd.to_datetime(value, utc=True).timestamp())


def normalize_strategy_config(raw_config: str | dict[str, Any] | None) -> dict[str, Any]:
    if raw_config in (None, "", {}):
        return {}
    if isinstance(raw_config, str):
        return json.loads(raw_config)
    return copy.deepcopy(raw_config)


def build_run_config(
    project: Project,
    strategy_config: dict[str, Any],
    window_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = load_base_config()
    config["backtest"]["symbol"] = project.symbol

    if window_override:
        config["windows"].update(window_override)

    if strategy_config:
        if "strategy" in strategy_config:
            config["strategy"] = strategy_config["strategy"]
            for section in ("risk", "visualization", "time", "backtest"):
                if section in strategy_config:
                    config[section] = strategy_config[section]
        else:
            config["strategy"] = strategy_config

    strategy_backtest = strategy_config.get("backtest") if isinstance(strategy_config, dict) else None
    if isinstance(strategy_backtest, dict):
        for key, value in strategy_backtest.items():
            config["backtest"][key] = value

    return config


async def enqueue_run(
    strategy: Strategy,
    project: Project,
    db: AsyncSession,
    window_override: dict[str, Any] | None = None,
) -> Run:
    run = Run(strategy_id=strategy.id, status="pending")
    db.add(run)
    await db.commit()
    await db.refresh(run)

    config = build_run_config(
        project=project,
        strategy_config=normalize_strategy_config(strategy.config_json),
        window_override=window_override,
    )
    asyncio.get_running_loop().run_in_executor(_executor, _run_worker, str(run.id), config)
    return run


def _run_worker(run_id: str, config: dict[str, Any]) -> None:
    asyncio.run(_run_worker_async(run_id, config))


async def _run_worker_async(run_id: str, config: dict[str, Any]) -> None:
    async with async_session_maker() as session:
        run = await session.scalar(select(Run).where(Run.id == run_id))
        if run is None:
            return
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        await session.commit()

    try:
        run_data = _execute_backtest(config)
    except Exception as exc:  # pragma: no cover - exercised through integration
        await _mark_run_failed(run_id, str(exc))
        return

    await _mark_run_complete(run_id, run_data)


def _execute_backtest(config: dict[str, Any]) -> dict[str, Any]:
    import run as run_module

    config_path = ROOT_DIR / settings.config_template_path
    serialized = yaml.safe_dump(config, sort_keys=False, allow_unicode=True)

    with _config_lock:
        original = config_path.read_text(encoding="utf-8")
        try:
            config_path.write_text(serialized, encoding="utf-8")
            return run_module.run_backtest_full()
        finally:
            config_path.write_text(original, encoding="utf-8")


async def _mark_run_complete(run_id: str, run_data: dict[str, Any]) -> None:
    async with async_session_maker() as session:
        run = await session.scalar(select(Run).where(Run.id == run_id))
        if run is None:
            return

        train_metrics = run_data.get("train", {}).get("metrics", {})
        validation_metrics = run_data.get("validation", {}).get("metrics", {})
        train_perf = train_metrics.get("performance", {})
        val_perf = validation_metrics.get("performance", {})
        train_risk = train_metrics.get("risk", {})
        val_risk = validation_metrics.get("risk", {})
        train_trades = train_metrics.get("trades", {})
        val_trades = validation_metrics.get("trades", {})

        run.status = "complete"
        run.run_number = run_data.get("run")
        run.result_path = run_data.get("artifacts", {}).get("run_json")
        run.train_sharpe = train_perf.get("sharpe")
        run.val_sharpe = val_perf.get("sharpe")
        run.train_return = train_perf.get("total_return")
        run.val_return = val_perf.get("total_return")
        run.train_drawdown = train_risk.get("max_drawdown")
        run.val_drawdown = val_risk.get("max_drawdown")
        run.train_trades = train_trades.get("num_trades")
        run.val_trades = val_trades.get("num_trades")
        run.config_hash = run_data.get("hashes", {}).get("config")
        run.completed_at = datetime.now(timezone.utc)

        await session.commit()


async def _mark_run_failed(run_id: str, error_message: str) -> None:
    async with async_session_maker() as session:
        run = await session.scalar(select(Run).where(Run.id == run_id))
        if run is None:
            return
        run.status = "failed"
        run.error_msg = error_message[:2000]
        run.completed_at = datetime.now(timezone.utc)
        await session.commit()
