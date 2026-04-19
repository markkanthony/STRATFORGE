"""
ui/data/projects.py — Project metadata for the home page.

Currently surfaces a single "default" project from config.yaml + history.jsonl.
Ready for multi-project expansion: add entries to return multiple dicts.
"""

from pathlib import Path
from typing import Optional
import yaml

from ui.data.loader import load_history

_ROOT        = Path(__file__).parent.parent.parent
_CONFIG_PATH = _ROOT / "config.yaml"


def load_config() -> dict:
    """Load and return config.yaml as a dict. Returns {} on missing file."""
    if not _CONFIG_PATH.exists():
        return {}
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def list_projects() -> list:
    """Return a list of project metadata dicts (one per configured project)."""
    history = load_history()
    config  = load_config()

    bt        = config.get("backtest", {})
    symbol    = bt.get("symbol", "EURUSD")
    timeframe = bt.get("timeframe", "H1")
    mode      = config.get("strategy", {}).get("mode", "hybrid")

    if not history:
        return [{
            "id":               "default",
            "name":             "Default Strategy",
            "symbol":           symbol,
            "timeframe":        timeframe,
            "mode":             mode,
            "run_count":        0,
            "best_sharpe":      None,
            "last_run":         None,
            "last_val_return":  None,
            "last_val_drawdown":None,
            "last_win_rate":    None,
            "last_val_trades":  None,
        }]

    best_sharpe = max((h.get("val_sharpe") or 0) for h in history)
    last        = history[0]   # history is newest-first

    return [{
        "id":                "default",
        "name":              "Default Strategy",
        "symbol":            last.get("symbol", symbol),
        "timeframe":         timeframe,
        "mode":              mode,
        "run_count":         len(history),
        "best_sharpe":       round(best_sharpe, 3),
        "last_run":          last.get("timestamp", "")[:10],
        "last_val_return":   last.get("val_return"),
        "last_val_drawdown": last.get("val_drawdown"),
        "last_win_rate":     None,   # not stored in history.jsonl
        "last_val_trades":   last.get("val_trades"),
        "last_val_sharpe":   last.get("val_sharpe"),
        "last_train_sharpe": last.get("train_sharpe"),
    }]
