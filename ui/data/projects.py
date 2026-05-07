"""
ui/data/projects.py — Project metadata for the home page.

Currently surfaces a single "default" project from config.yaml + history.jsonl.
Ready for multi-project expansion: add entries to return multiple dicts.
"""

import json
import re
from pathlib import Path
from typing import Optional
import yaml

from ui.data.loader import load_history

_ROOT         = Path(__file__).parent.parent.parent
_CONFIG_PATH  = _ROOT / "config.yaml"
_RESULTS_DIR  = _ROOT / "results"
_STRATEGY_PATH = _ROOT / "strategy.py"


def load_strategy_history() -> list:
    """
    Return per-run strategy history (newest first) enriched with change_type
    from run_NNN.diff.json files.
    """
    history = load_history()  # newest-first list
    rows_oldest_first = list(reversed(history))
    prev_sharpe = None
    result = []

    for entry in rows_oldest_first:
        run_num = entry.get("run")
        val_sharpe = entry.get("val_sharpe")
        val_drawdown = entry.get("val_drawdown")
        val_trades = entry.get("val_trades")

        change_type = None
        if run_num is not None:
            diff_path = _RESULTS_DIR / f"run_{run_num:03d}.diff.json"
            if diff_path.exists():
                try:
                    diff = json.loads(diff_path.read_text(encoding="utf-8"))
                    change_type = diff.get("change_type")
                except Exception:
                    pass

        delta = None
        if val_sharpe is not None and prev_sharpe is not None:
            delta = round(val_sharpe - prev_sharpe, 3)

        result.append({
            "run": run_num,
            "val_sharpe": val_sharpe,
            "val_drawdown": val_drawdown,
            "val_trades": val_trades,
            "change_type": change_type,
            "delta_sharpe": delta,
        })

        if val_sharpe is not None:
            prev_sharpe = val_sharpe

    return list(reversed(result))  # newest-first


def build_strategy_prompt(config: dict, history: list) -> str:
    """Build a token-efficient prompt for AI strategy optimization."""
    strategy = config.get("strategy", {})
    current_config_yaml = yaml.dump(strategy, default_flow_style=False).strip()

    recent = [h for h in history if h.get("val_sharpe") is not None][:3]
    table_lines = []
    for h in recent:
        run_n = str(h.get("run", "?")).rjust(3)
        sharpe = f"{h['val_sharpe']:.2f}".rjust(6) if h.get("val_sharpe") is not None else "    —"
        dd_val = h.get("val_drawdown")
        dd = f"{dd_val * 100:.1f}%".rjust(6) if dd_val is not None else "    —"
        trades = str(h.get("val_trades", "—")).rjust(6)
        table_lines.append(f"  {run_n} | {sharpe} | {dd} | {trades}")

    history_table = "\n".join(table_lines) if table_lines else "  No runs yet"

    return f"""# StratForge: Improve Strategy

## Toolkit (use via config — no code needed)
indicators: fast_ema, slow_ema, rsi_period, atr_period
patterns: bullish_engulfing, bearish_engulfing, sweep_prev_high,
          sweep_prev_low, inside_bar_breakout, orb{{enabled, bars}}
context: use_prev_day_levels, use_session_filter, trend_filter
exits: atr_sl_multiplier, atr_tp_multiplier

## Current strategy config
{current_config_yaml}

## Validation run history (last 3)
  Run | Sharpe |     DD | Trades
{history_table}

## Instructions
Improve validation Sharpe. Return ONE block only — no explanation outside it.

Config change (existing toolkit sufficient):
  change_type: config
  strategy:
    [only changed fields in YAML]

Code change (new logic needed):
  change_type: code
  def generate_signals(df, config):
      # df cols: open, high, low, close, volume (datetime index or time col)
      # must add cols: signal (-1/0/1), sl_price, tp_price
      # use shift(1) for all pattern lookbacks — no lookahead
      ..."""


def parse_ai_output(text: str) -> dict:
    """
    Parse AI response and return one of:
      {"type": "config",  "strategy": dict}
      {"type": "code",    "code": str}
      {"type": "error",   "message": str}
    """
    # Strip markdown fences
    text = re.sub(r"```[a-zA-Z]*\n?", "", text).strip()

    # --- Config change ---
    if "change_type: config" in text:
        try:
            lines = text.split("\n")
            yaml_lines = []
            in_block = False
            for line in lines:
                if "change_type: config" in line:
                    in_block = True
                    continue
                if in_block:
                    if "change_type:" in line and "change_type: config" not in line:
                        break
                    yaml_lines.append(line)
            parsed = yaml.safe_load("\n".join(yaml_lines))
            if isinstance(parsed, dict):
                strategy = parsed.get("strategy", parsed)
                if isinstance(strategy, dict):
                    return {"type": "config", "strategy": strategy}
        except Exception:
            pass

    # --- Code change ---
    if "change_type: code" in text and "def generate_signals" in text:
        match = re.search(r"(def generate_signals\s*\(.*)", text, re.DOTALL)
        if match:
            code = match.group(1).strip()
            if "return" in code:
                return {"type": "code", "code": code}

    # --- JSON fallback ---
    decoder = json.JSONDecoder()
    idx = text.find("{")
    while idx != -1:
        try:
            obj, _ = decoder.raw_decode(text, idx)
            if isinstance(obj, dict):
                ct = obj.get("change_type")
                if ct == "config" and "strategy" in obj:
                    return {"type": "config", "strategy": obj["strategy"]}
                if ct == "code" and "code" in obj:
                    return {"type": "code", "code": obj["code"]}
            break
        except json.JSONDecodeError:
            idx = text.find("{", idx + 1)

    return {
        "type": "error",
        "message": (
            "Could not detect change_type. "
            "Ensure output starts with 'change_type: config' or 'change_type: code'."
        ),
    }


def apply_ai_output(parsed: dict) -> None:
    """Write parsed AI output to config.yaml (config) or strategy.py (code)."""
    if parsed["type"] == "config":
        config = load_config()
        config["strategy"] = parsed["strategy"]
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    elif parsed["type"] == "code":
        module = (
            '"""strategy.py — AI-generated via StratForge"""\n'
            "import numpy as np\n"
            "import pandas as pd\n\n\n"
            + parsed["code"]
            + "\n"
        )
        with open(_STRATEGY_PATH, "w", encoding="utf-8") as f:
            f.write(module)

    else:
        raise ValueError(parsed.get("message", "Invalid parsed output"))


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
