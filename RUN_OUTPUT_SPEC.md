# Run Output Specification

This document explains the output structure of `run.py` for StratForge backtester.

## Output Files

### 1. `results/run_NNN.json`

Complete run result with all data. Example structure:

```json
{
  "run": 1,
  "timestamp": "2024-04-19T17:55:00.000000+00:00",
  "symbol": "EURUSD",
  "timeframe": "H1",
  "timezones": {
    "data_timezone": "broker",
    "system_timezone": "UTC",
    "display_timezone": "Asia/Manila",
    "session_timezone": "Asia/Manila"
  },
  "windows": {
    "train": {
      "start": "2023-01-01",
      "end": "2023-06-30",
      "bars": 3000,
      "signals": 45
    },
    "validation": {
      "start": "2023-07-01",
      "end": "2023-12-31",
      "bars": 3100,
      "signals": 38
    }
  },
  "train": {
    "trades": [
      {
        "trade_id": 1,
        "side": "long",
        "entry_time": "2023-01-05T10:00:00+00:00",
        "exit_time": "2023-01-06T14:00:00+00:00",
        "entry_price": 1.0650,
        "exit_price": 1.0680,
        "sl_price": 1.0630,
        "tp_price": 1.0690,
        "size": 0.10,
        "risk_pct": 1.0,
        "pnl": 30.0,
        "pnl_pct": 0.3,
        "r_multiple": 1.5,
        "bars_held": 28,
        "entry_session": "london",
        "exit_reason": "tp_hit"
      }
    ],
    "equity_curve": [
      {"time": "2023-01-01T00:00:00+00:00", "equity": 10000.0},
      {"time": "2023-01-02T00:00:00+00:00", "equity": 10000.0}
    ],
    "metrics": {
      "performance": {
        "total_return": 0.15,
        "annualized_return": 0.32,
        "sharpe": 1.45,
        "sortino": 2.10,
        "calmar": 1.80
      },
      "risk": {
        "max_drawdown": -0.08,
        "avg_drawdown": -0.03,
        "max_drawdown_duration_bars": 150,
        "time_to_recover_bars": 120,
        "ulcer_index": 0.04,
        "recovery_factor": 1.87,
        "return_on_max_drawdown": 1.87
      },
      "trades": {
        "num_trades": 45,
        "win_rate": 0.55,
        "loss_rate": 0.45,
        "profit_factor": 1.65,
        "expectancy": 35.5,
        "avg_win": 85.0,
        "avg_loss": -52.0,
        "payoff_ratio": 1.63,
        "avg_r_multiple": 0.85,
        "best_trade": 250.0,
        "worst_trade": -120.0,
        "median_trade_return": 25.0,
        "std_trade_return": 75.0,
        "avg_trade_bars": 32,
        "trades_per_month": 7.5
      },
      "streaks": {
        "max_consecutive_wins": 6,
        "max_consecutive_losses": 4,
        "avg_consecutive_wins": 2.5,
        "avg_consecutive_losses": 2.0,
        "current_consecutive_wins": 2,
        "current_consecutive_losses": 0
      },
      "side_breakdown": {
        "long_trades": 23,
        "short_trades": 22,
        "long_win_rate": 0.57,
        "short_win_rate": 0.54,
        "long_profit_factor": 1.72,
        "short_profit_factor": 1.58
      },
      "diagnostics": {},
      "risk_sizing": {
        "avg_position_size": 0.10,
        "max_position_size": 0.12,
        "min_position_size": 0.08,
        "avg_risk_pct_per_trade": 1.0,
        "max_risk_pct_per_trade": 1.2,
        "sizing_model_used": "fixed_fractional",
        "kelly_estimate": null,
        "kelly_fraction_applied": null,
        "fallback_to_fixed_fractional_count": 0,
        "risk_halt_triggered": false
      }
    }
  },
  "validation": {
    "trades": [],
    "equity_curve": [],
    "metrics": {}
  },
  "config_snapshot": {
    "time": {},
    "backtest": {},
    "windows": {},
    "strategy": {},
    "risk": {},
    "visualization": {}
  },
  "hashes": {
    "config": "abc123def456...",
    "strategy": "789ghi012jkl..."
  },
  "artifacts": {
    "run_json": "results/run_001.json",
    "visualization_dir": "results/run_001/"
  }
}
```

### 2. `results/latest.json`

Quick summary of most recent run:

```json
{
  "run": 1,
  "timestamp": "2024-04-19T17:55:00.000000+00:00",
  "symbol": "EURUSD",
  "timeframe": "H1",
  "train_metrics": {
    "sharpe": 1.45,
    "total_return": 0.15,
    "max_drawdown": -0.08,
    "num_trades": 45
  },
  "validation_metrics": {
    "sharpe": 1.32,
    "total_return": 0.12,
    "max_drawdown": -0.10,
    "num_trades": 38
  },
  "path": "results\\run_001.json"
}
```

### 3. `results/history.jsonl`

One line per run (JSON Lines format):

```jsonl
{"run": 1, "timestamp": "2024-04-19T17:55:00+00:00", "symbol": "EURUSD", "timeframe": "H1", "train_sharpe": 1.45, "val_sharpe": 1.32, "train_return": 0.15, "val_return": 0.12, "train_drawdown": -0.08, "val_drawdown": -0.10, "train_trades": 45, "val_trades": 38, "config_hash": "abc123...", "strategy_hash": "789def..."}
{"run": 2, "timestamp": "2024-04-19T18:10:00+00:00", "symbol": "EURUSD", "timeframe": "H1", "train_sharpe": 1.52, "val_sharpe": 1.28, "train_return": 0.18, "val_return": 0.11, "train_drawdown": -0.07, "val_drawdown": -0.11, "train_trades": 42, "val_trades": 35, "config_hash": "def456...", "strategy_hash": "abc789..."}
```

## Run Numbering

- Run numbers start at 1
- `get_next_run_number()` scans existing `run_*.json` files
- Returns `max(existing_runs) + 1`
- Creates results directory if it doesn't exist
- Zero-padded to 3 digits in filenames: `run_001.json`, `run_002.json`, etc.

## latest.json Update Logic

The `latest.json` file is completely overwritten on each run with the most recent run's summary data. This provides quick access to the last run's key metrics without parsing the full run_NNN.json file.

## history.jsonl Append Logic

Each run appends a single JSON line to `history.jsonl`. This creates a time-series log of all runs for:
- Trend analysis
- Performance comparison
- AI loop optimization tracking
- Detecting plateaus and overfitting

The file can be read line-by-line or loaded as a list of dictionaries.

## Visualization Artifacts

When `visualization.enabled: true` in config:

```
results/run_001/
├── summary.html
├── train_price_chart.png
├── validation_price_chart.png
├── train_equity_curve.png
├── validation_equity_curve.png
├── train_drawdown.png
├── validation_drawdown.png
├── trade_returns_hist.png
├── r_multiples_hist.png
└── ... (additional charts based on visualization.mode)
```

## Error Handling

- If validation fails, run terminates with clear error message
- Zero trades is handled gracefully (metrics return safe defaults)
- Missing data raises `ValueError` with specific window information
- Visualization errors are non-fatal (logged as warnings)

## Determinism Guarantees

1. Same config + same strategy code + same data = same results
2. Config and strategy hashes stored for reproducibility
3. All timestamps are UTC internally
4. No randomness in backtest engine
5. File writes are Windows-safe (no symlinks, proper path handling)

## Usage

```python
# Run from command line
python run.py

# Or import and use
from run import run_backtest_full

run_data = run_backtest_full()
print(f"Run {run_data['run']} complete")