# StratForge

A deterministic Python backtester with AI optimization loop.

## Phase 1: Project Scaffold ✓

This is the Phase 1 baseline with complete project structure and configuration.

## Project Structure

```
py-backtester-mk00/
├── requirements.txt          # Python dependencies
├── config.yaml              # Main configuration file
├── strategy.py              # Strategy signal generation
├── validator.py             # Strategy output validation
├── data_feed.py            # Market data loading (MT5 + CSV)
├── risk_manager.py         # Position sizing and risk enforcement
├── backtest_engine.py      # Deterministic backtest engine
├── metrics.py              # Performance metrics calculation
├── plotter.py              # Optional visualization layer
├── run.py                  # Main orchestrator
├── ai_loop.py              # AI optimization loop
├── data/
│   └── fallback.csv        # Fallback market data
└── results/                # Backtest results output
```

## Configuration

The `config.yaml` file contains five main sections:

1. **time**: Timezone settings for data, system, display, and session
2. **backtest**: Symbol, timeframe# STRATFORGE
