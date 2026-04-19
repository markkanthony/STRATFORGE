"""
run.py - Deterministic backtest orchestrator

This module runs a single backtest iteration:
1. Loads config
2. Determines next run number
3. Fetches full data from train_start to validation_end
4. Splits into train and validation windows
5. Runs strategy.generate_signals on each window
6. Validates outputs using validator.py
7. Runs backtest on each window
8. Computes metrics on each window
9. Saves structured outputs
10. Optionally generates visual artifacts
11. Updates latest.json
12. Appends to history.jsonl

Windows-safe, deterministic, no symlinks.
"""

import json
import hashlib
import sys
import yaml
from pathlib import Path
from datetime import datetime, timezone, date
from typing import Dict, Any, Optional
import pandas as pd


class _SafeJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles date/datetime and numpy scalars."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        try:
            import numpy as np
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        return super().default(obj)

# Ensure UTF-8 output on Windows (handles ✓ ✗ etc. in print statements)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Import project modules
from core import data_feed
import strategy as strategy_module
from strategy import BaseStrategy, ConfigStrategy
from core import validator
from core import risk_manager
from core import backtest_engine
from core import metrics
from viz import plotter


def load_config(config_path: Path = Path("config.yaml")) -> dict:
    """Load and parse config.yaml"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


def get_next_run_number(results_dir: Path) -> int:
    """
    Determine next run number by scanning results directory.
    Returns 1 if no runs exist, otherwise max(existing) + 1.
    """
    if not results_dir.exists():
        results_dir.mkdir(parents=True, exist_ok=True)
        return 1
    
    existing_runs = []
    for file in results_dir.glob("run_*.json"):
        try:
            num = int(file.stem.split("_")[1])
            existing_runs.append(num)
        except (IndexError, ValueError):
            continue
    
    if not existing_runs:
        return 1
    
    return max(existing_runs) + 1


def compute_hash(data: str) -> str:
    """Compute SHA256 hash of string data"""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def save_json_safe(data: dict, path: Path) -> None:
    """Save JSON with Windows-safe write and date/numpy serialization."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, cls=_SafeJSONEncoder)


def append_jsonl_safe(data: dict, path: Path) -> None:
    """Append single JSON line to JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, cls=_SafeJSONEncoder) + "\n")


def run_backtest_full(strategy: Optional[BaseStrategy] = None) -> Dict[str, Any]:
    """
    Main orchestrator function.
    Runs complete backtest flow and returns run metadata.

    Args:
        strategy: Optional BaseStrategy instance. If None, defaults to
                  ConfigStrategy(config) — the YAML-driven pipeline.
                  Pass a ComposableStrategy (or any BaseStrategy subclass)
                  to use a programmatic strategy instead.
    """
    print("=" * 80)
    print("StratForge - Deterministic Backtester")
    print("=" * 80)
    
    # Step 1: Load config
    print("\n[1/12] Loading config...")
    config_path = Path("config.yaml")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    config = load_config(config_path)
    print(f"  ✓ Config loaded")
    
    # Step 2: Determine next run number
    print("\n[2/12] Determining run number...")
    results_dir = Path("results")
    run_number = get_next_run_number(results_dir)
    print(f"  ✓ Run number: {run_number}")
    
    # Step 3: Fetch full data
    print("\n[3/12] Fetching market data...")
    symbol = config["backtest"]["symbol"]
    timeframe = config["backtest"]["timeframe"]
    train_start = config["windows"]["train_start"]
    train_end = config["windows"]["train_end"]
    val_start = config["windows"]["validation_start"]
    val_end = config["windows"]["validation_end"]
    
    # Fetch data from train_start to validation_end
    full_df = data_feed.get_ohlcv(
        symbol=symbol,
        timeframe=timeframe,
        start_date=train_start,
        end_date=val_end,
        config=config
    )
    print(f"  ✓ Fetched {len(full_df)} bars from {train_start} to {val_end}")
    
    # Step 4: Split into train and validation
    print("\n[4/12] Splitting data into train and validation windows...")
    train_df = full_df[
        (full_df["time"] >= pd.Timestamp(train_start, tz="UTC")) &
        (full_df["time"] <= pd.Timestamp(train_end, tz="UTC"))
    ].copy()
    
    val_df = full_df[
        (full_df["time"] >= pd.Timestamp(val_start, tz="UTC")) &
        (full_df["time"] <= pd.Timestamp(val_end, tz="UTC"))
    ].copy()
    
    print(f"  ✓ Train: {len(train_df)} bars ({train_start} to {train_end})")
    print(f"  ✓ Validation: {len(val_df)} bars ({val_start} to {val_end})")
    
    if len(train_df) == 0:
        raise ValueError("Train window contains no data")
    if len(val_df) == 0:
        raise ValueError("Validation window contains no data")
    
    # Step 5: Resolve strategy instance and generate signals
    if strategy is None:
        strategy = ConfigStrategy(config)

    print("\n[5/12] Generating signals...")
    print(f"  → Strategy: {strategy.name}")
    print("  → Running strategy on train window...")
    train_signals = strategy.generate_signals(train_df)
    print(f"    ✓ Train signals: {len(train_signals)} rows, {(train_signals['signal'] != 0).sum()} signals")

    print("  → Running strategy on validation window...")
    val_signals = strategy.generate_signals(val_df)
    print(f"    ✓ Validation signals: {len(val_signals)} rows, {(val_signals['signal'] != 0).sum()} signals")
    
    # Step 6: Validate outputs
    # Pass config only for ConfigStrategy so the lookahead smoke test can re-run
    # the same strategy on a truncated dataset. For ComposableStrategy the test
    # is skipped (validator warns) because the strategy object, not config, holds
    # the logic — re-running it on truncated data still works structurally.
    val_config = config if isinstance(strategy, ConfigStrategy) else None

    print("\n[6/12] Validating strategy outputs...")
    train_valid, train_errors = validator.validate_strategy_output(train_df, train_signals, val_config)
    if not train_valid:
        error_msg = "Train validation failed:\n" + "\n".join(train_errors)
        print(f"  ✗ {error_msg}")
        raise ValueError(error_msg)
    print("  ✓ Train validation passed")

    val_valid, val_errors = validator.validate_strategy_output(val_df, val_signals, val_config)
    if not val_valid:
        error_msg = "Validation validation failed:\n" + "\n".join(val_errors)
        print(f"  ✗ {error_msg}")
        raise ValueError(error_msg)
    print("  ✓ Validation validation passed")
    
    # Step 7: Run backtest on each window
    print("\n[7/12] Running backtests...")
    print("  → Running train backtest...")
    train_result = backtest_engine.run_backtest(train_signals, config, "train")
    print(f"    ✓ Train complete: {len(train_result['trades'])} trades")
    
    print("  → Running validation backtest...")
    val_result = backtest_engine.run_backtest(val_signals, config, "validation")
    print(f"    ✓ Validation complete: {len(val_result['trades'])} trades")
    
    # Step 8: Compute metrics on each window
    print("\n[8/12] Computing metrics...")
    train_metrics = metrics.compute_metrics(
        backtest_result=train_result,
        config=config,
        run_number=run_number,
        window_label="train"
    )
    print("  ✓ Train metrics computed")

    val_metrics = metrics.compute_metrics(
        backtest_result=val_result,
        config=config,
        run_number=run_number,
        window_label="validation"
    )
    print("  ✓ Validation metrics computed")
    
    # Step 9: Save structured outputs
    print("\n[9/12] Preparing run data...")
    
    # Compute hashes for reproducibility
    config_str = json.dumps(config, sort_keys=True, cls=_SafeJSONEncoder)
    config_hash = compute_hash(config_str)
    
    strategy_path = Path("strategy.py")
    if strategy_path.exists():
        strategy_code = strategy_path.read_text(encoding="utf-8")
        strategy_hash = compute_hash(strategy_code)
    else:
        strategy_hash = None
    
    # Build comprehensive run data
    run_data = {
        "run": run_number,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "strategy_name": strategy.name,
        "symbol": symbol,
        "timeframe": timeframe,
        "timezones": {
            "data_timezone": config["time"]["data_timezone"],
            "system_timezone": config["time"]["system_timezone"],
            "display_timezone": config["time"]["display_timezone"],
            "session_timezone": config["time"]["session_timezone"]
        },
        "windows": {
            "train": {
                "start": train_start,
                "end": train_end,
                "bars": len(train_df),
                "signals": int((train_signals["signal"] != 0).sum())
            },
            "validation": {
                "start": val_start,
                "end": val_end,
                "bars": len(val_df),
                "signals": int((val_signals["signal"] != 0).sum())
            }
        },
        "train": {
            "trades": train_result["trades"],
            "equity_curve": train_result["equity_curve"],
            "metrics": train_metrics
        },
        "validation": {
            "trades": val_result["trades"],
            "equity_curve": val_result["equity_curve"],
            "metrics": val_metrics
        },
        "config_snapshot": config,
        "hashes": {
            "config": config_hash,
            "strategy": strategy_hash
        },
        "artifacts": {
            "run_json": f"results/run_{run_number:03d}.json",
            "visualization_dir": f"results/run_{run_number:03d}/" if config.get("visualization", {}).get("enabled", False) else None
        }
    }
    
    print("  ✓ Run data prepared")
    
    # Save run_NNN.json
    run_json_path = results_dir / f"run_{run_number:03d}.json"
    save_json_safe(run_data, run_json_path)
    print(f"  ✓ Saved: {run_json_path}")
    
    # Step 10: Generate visual artifacts if enabled
    print("\n[10/12] Generating visual artifacts...")
    if config.get("visualization", {}).get("enabled", False):
        viz_dir = results_dir / f"run_{run_number:03d}"
        viz_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            plotter.generate_visual_artifacts(run_data, config, viz_dir)
            print(f"  ✓ Visual artifacts saved to: {viz_dir}")
        except Exception as e:
            print(f"  ⚠ Visualization failed (non-fatal): {e}")
    else:
        print("  → Visualization disabled in config")
    
    # Step 11: Update latest.json
    print("\n[11/12] Updating latest.json...")
    latest_json_path = results_dir / "latest.json"
    latest_data = {
        "run": run_number,
        "timestamp": run_data["timestamp"],
        "symbol": symbol,
        "timeframe": timeframe,
        "train_metrics": {
            "sharpe": train_metrics.get("performance", {}).get("sharpe"),
            "total_return": train_metrics.get("performance", {}).get("total_return"),
            "max_drawdown": train_metrics.get("risk", {}).get("max_drawdown"),
            "num_trades": train_metrics.get("trades", {}).get("num_trades")
        },
        "validation_metrics": {
            "sharpe": val_metrics.get("performance", {}).get("sharpe"),
            "total_return": val_metrics.get("performance", {}).get("total_return"),
            "max_drawdown": val_metrics.get("risk", {}).get("max_drawdown"),
            "num_trades": val_metrics.get("trades", {}).get("num_trades")
        },
        "path": str(run_json_path)
    }
    save_json_safe(latest_data, latest_json_path)
    print(f"  ✓ Updated: {latest_json_path}")
    
    # Step 12: Append to history.jsonl
    print("\n[12/12] Appending to history.jsonl...")
    history_path = results_dir / "history.jsonl"
    history_entry = {
        "run": run_number,
        "timestamp": run_data["timestamp"],
        "symbol": symbol,
        "timeframe": timeframe,
        "train_sharpe": train_metrics.get("performance", {}).get("sharpe"),
        "val_sharpe": val_metrics.get("performance", {}).get("sharpe"),
        "train_return": train_metrics.get("performance", {}).get("total_return"),
        "val_return": val_metrics.get("performance", {}).get("total_return"),
        "train_drawdown": train_metrics.get("risk", {}).get("max_drawdown"),
        "val_drawdown": val_metrics.get("risk", {}).get("max_drawdown"),
        "train_trades": train_metrics.get("trades", {}).get("num_trades"),
        "val_trades": val_metrics.get("trades", {}).get("num_trades"),
        "config_hash": config_hash,
        "strategy_hash": strategy_hash
    }
    append_jsonl_safe(history_entry, history_path)
    print(f"  ✓ Appended to: {history_path}")
    
    # Final summary
    print("\n" + "=" * 80)
    print("Run complete!")
    print("=" * 80)
    print(f"Run number: {run_number}")
    print(f"Train trades: {len(train_result['trades'])}")
    print(f"Validation trades: {len(val_result['trades'])}")
    print(f"Train Sharpe: {train_metrics.get('performance', {}).get('sharpe', 'N/A')}")
    print(f"Validation Sharpe: {val_metrics.get('performance', {}).get('sharpe', 'N/A')}")
    print(f"Results saved to: {run_json_path}")
    print("=" * 80)
    
    return run_data


def main() -> None:
    """
    Main entry point for running a backtest.
    Handles errors and provides clear output.
    """
    try:
        run_data = run_backtest_full()
        print("\n✓ Backtest completed successfully")
        return run_data
    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
        print("Please ensure config.yaml and required data files exist.")
        raise
    except ValueError as e:
        print(f"\n✗ Validation Error: {e}")
        raise
    except Exception as e:
        print(f"\n✗ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
