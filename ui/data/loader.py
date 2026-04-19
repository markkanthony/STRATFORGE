"""
ui/data/loader.py — Pure Python data-access layer for the StratForge UI.

No Dash dependency. All functions are independently testable.
Expensive calls are wrapped with functools.lru_cache.
"""

import io
import json
import sys
import functools
from pathlib import Path
from typing import Optional

import pandas as pd

# Ensure project root is on sys.path so core/* imports work
_ROOT = Path(__file__).parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_RESULTS_DIR = _ROOT / "results"


# ------------------------------------------------------------------ #
# History                                                              #
# ------------------------------------------------------------------ #

def load_history() -> list:
    """
    Read results/history.jsonl and return a list of dicts, newest first.
    Returns empty list if file does not exist.
    """
    path = _RESULTS_DIR / "history.jsonl"
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return list(reversed(rows))


# ------------------------------------------------------------------ #
# Run JSON                                                             #
# ------------------------------------------------------------------ #

@functools.lru_cache(maxsize=20)
def _load_run_json_cached(run_number: int) -> str:
    """Return raw JSON string (lru_cache needs hashable args)."""
    path = _RESULTS_DIR / f"run_{run_number:03d}.json"
    return path.read_text(encoding="utf-8")


def load_run_json(run_number: int) -> Optional[dict]:
    """
    Load results/run_NNN.json and return as dict.
    Returns None if file does not exist.
    """
    path = _RESULTS_DIR / f"run_{run_number:03d}.json"
    if not path.exists():
        return None
    try:
        return json.loads(_load_run_json_cached(run_number))
    except Exception:
        return None


def get_latest_run_number() -> Optional[int]:
    """Return the highest run number found in results/, or None."""
    path = _RESULTS_DIR / "latest.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("run")
        except Exception:
            pass
    # Fallback: scan directory
    runs = []
    for f in _RESULTS_DIR.glob("run_*.json"):
        try:
            runs.append(int(f.stem.split("_")[1]))
        except (IndexError, ValueError):
            pass
    return max(runs) if runs else None


# ------------------------------------------------------------------ #
# OHLCV                                                                #
# ------------------------------------------------------------------ #

@functools.lru_cache(maxsize=4)
def _load_ohlcv_cached(symbol: str, timeframe: str, start: str, end: str, config_json: str) -> str:
    """Inner cached loader — returns JSON string of the DataFrame."""
    from core import data_feed
    config = json.loads(config_json)
    df = data_feed.get_ohlcv(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start,
        end_date=end,
        config=config,
    )
    return df.to_json(orient="records", date_format="iso")


def load_ohlcv_for_run(run_data: dict, window: str) -> pd.DataFrame:
    """
    Load OHLCV bars for the given run + window using the stored config_snapshot.
    Cached by (symbol, timeframe, window start, window end).
    """
    windows = run_data["windows"][window]
    symbol = run_data["symbol"]
    timeframe = run_data["timeframe"]
    start = str(windows["start"])
    end = str(windows["end"])
    config_json = json.dumps(run_data["config_snapshot"], sort_keys=True)

    try:
        raw = _load_ohlcv_cached(symbol, timeframe, start, end, config_json)
        df = pd.read_json(io.StringIO(raw), orient="records")
        # Ensure time column is datetime
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"], utc=True)
        return df
    except Exception as exc:
        print(f"[loader] OHLCV load failed: {exc}")
        return pd.DataFrame()


# ------------------------------------------------------------------ #
# Trades & equity                                                       #
# ------------------------------------------------------------------ #

def get_trades(run_data: dict, window: str) -> list:
    """
    Extract trades from run_data[window]["trades"].
    Injects a 0-based trade_idx field for cross-referencing.
    Returns empty list if run_data is None.
    """
    if run_data is None:
        return []
    trades = run_data.get(window, {}).get("trades", [])
    return [dict(t, trade_idx=i) for i, t in enumerate(trades)]


def get_equity(run_data: dict, window: str) -> list:
    """
    Extract equity_curve from run_data[window]["equity_curve"].
    Returns empty list if run_data is None.
    """
    if run_data is None:
        return []
    return run_data.get(window, {}).get("equity_curve", [])


def get_metrics(run_data: dict, window: str) -> dict:
    """Return the metrics dict for a given window, or {}."""
    if run_data is None:
        return {}
    return run_data.get(window, {}).get("metrics", {})
