# StratForge

A deterministic Python backtester with AI optimization loop. Supports indicator-driven, pattern-driven, and hybrid strategies with pluggable risk models and optional visualization.

---

## Requirements

- Python 3.11+
- MetaTrader 5 (optional — CSV fallback works without it)
- An [Anthropic API key](https://console.anthropic.com/) (only required for `ai_loop.py`)

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/markkanthony/STRATFORGE.git
cd STRATFORGE

# 2. Create and activate a virtual environment (recommended)
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Quick Start

```bash
python run.py
```

That's it. The orchestrator runs the full 12-step pipeline and prints progress to the console.

**Expected output:**

```
[1/12] Loading config...         ✓ Config loaded
[2/12] Determining run number... ✓ Run number: 1
[3/12] Fetching market data...   ✓ Fetched 6240 bars
[4/12] Splitting windows...      ✓ Train: 3097 bars / Validation: 3120 bars
[5/12] Generating signals...     ✓ 194 train signals / 180 val signals
[6/12] Validating outputs...     ✓ Train validation passed / Val validation passed
[7/12] Running backtests...      ✓ 47 train trades / 64 val trades
[8/12] Computing metrics...      ✓ Done
[9/12] Saving results...         ✓ results/run_001.json
[10/12] Visualizations...        ✓ results/run_001/
[11/12] latest.json...           ✓ Updated
[12/12] history.jsonl...         ✓ Appended
```

**Output files:**

| Path | Description |
|------|-------------|
| `results/run_001.json` | Full run record with trades, metrics, config snapshot |
| `results/latest.json` | Lightweight summary of the most recent run |
| `results/history.jsonl` | Append-only log of every run (Sharpe, return, drawdown) |
| `results/run_001/*.png` | Chart images (equity curve, drawdown, histograms, etc.) |
| `results/run_001/summary.html` | HTML summary report |

---

## Data Sources

StratForge tries MT5 first, then falls back to CSV automatically.

**Option A — MetaTrader 5 (live broker data)**

1. Open MetaTrader 5 and log into your broker account.
2. Ensure the symbol in `config.yaml` (`backtest.symbol`) is subscribed in Market Watch.
3. Run `python run.py` — MT5 data is fetched automatically.

**Option B — CSV fallback (no MT5 required)**

Place a CSV file at `data/fallback.csv` with this header:

```
time,open,high,low,close,tick_volume
2023-01-02 00:00:00,1.07016,1.07027,1.07004,1.07016,2085
...
```

The repo ships with a synthetic 6 240-bar EURUSD H1 file covering all of 2023 so the backtester runs out of the box.

---

## Configuration

All settings live in `config.yaml`. The key sections:

### `backtest`
```yaml
backtest:
  symbol: EURUSD
  timeframe: H1
  capital: 10000
  spread: 1.0          # pips
  commission: 7.0      # USD round-trip
  slippage_pips: 0.5
```

### `windows`
```yaml
windows:
  train_start: 2023-01-01
  train_end:   2023-06-30
  validation_start: 2023-07-01
  validation_end:   2023-12-31
```

### `strategy`
```yaml
strategy:
  mode: hybrid   # indicator | pattern | hybrid
  indicators:
    fast_ema: 10
    slow_ema: 50
    rsi_period: 14
    atr_period: 14
  entry:
    long_require_all:
      - trend_up
      - sweep_prev_low
      - bullish_engulfing
    short_require_all:
      - trend_down
      - sweep_prev_high
      - bearish_engulfing
  exits:
    atr_sl_multiplier: 1.5
    atr_tp_multiplier: 2.0
```

### `risk`
```yaml
risk:
  model: fixed_fractional   # fixed_lot | fixed_fractional | volatility_adjusted | fractional_kelly
  fixed_fractional:
    risk_pct: 1.0
  constraints:
    max_positions: 1
    max_daily_loss_pct: 3.0
    max_drawdown_halt_pct: 15.0
    min_stop_pips: 3
    max_stop_pips: 100
```

### `visualization`
```yaml
visualization:
  enabled: true
  mode: detailed   # off | basic | detailed
```

---

## AI Optimization Loop

The AI loop reads the latest backtest results, proposes targeted changes to `config.yaml` and/or `strategy.py`, validates them, and reruns automatically.

**Setup:**

```bash
# Set your Anthropic API key
export ANTHROPIC_API_KEY=sk-ant-...   # macOS / Linux
set ANTHROPIC_API_KEY=sk-ant-...      # Windows
```

**Run:**

```bash
python ai_loop.py
```

The loop stops automatically when any of these conditions are met:

| Condition | Threshold |
|-----------|-----------|
| Validation Sharpe | > 2.0 |
| Validation max drawdown | < 15% |
| Overfit gap (train − val Sharpe) | < 1.0 for 3 consecutive runs |
| No improvement over last 8 runs | plateau |
| Hard cap | 50 iterations |

Results are saved to `results/run_NNN.diff.json` per iteration.

---

## Project Structure

```
STRATFORGE/
├── run.py               # Main orchestrator (run this)
├── ai_loop.py           # AI optimization loop
├── strategy.py          # Signal generation pipeline
├── validator.py         # Lookahead and signal integrity checks
├── risk_manager.py      # Position sizing and risk enforcement
├── backtest_engine.py   # Deterministic bar-by-bar engine
├── metrics.py           # Performance metrics (Sharpe, Calmar, etc.)
├── plotter.py           # Visualization layer (matplotlib)
├── data_feed.py         # MT5 + CSV data loader
├── config.yaml          # All settings
├── requirements.txt     # Python dependencies
├── data/
│   └── fallback.csv     # Synthetic EURUSD H1 data (2023)
└── results/             # Generated outputs (gitignored)
```

---

## Locking Rules

The following config sections are **read-only to the AI loop** and must only be changed manually:

- `backtest` — symbol, capital, costs
- `windows` — date ranges
- `time` — timezone settings
- `visualization` — chart settings
- `risk.constraints` — safety limits

Only `strategy` (and optionally `risk.model` / model params) may be modified by `ai_loop.py`.
