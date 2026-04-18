# StratForge Smoke Test Sequence

## Purpose
Quick validation that all modules integrate correctly after Phase 11 cleanup.

## Prerequisites
```bash
cd py-backtester-mk00
pip install -r requirements.txt
```

## Test Sequence

### 1. Config Load Test
**Purpose**: Verify config.yaml parses correctly

```python
import yaml
from pathlib import Path

config_path = Path("config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

print(f"✓ Config loaded: {config['backtest']['symbol']}")
print(f"✓ Strategy mode: {config['strategy']['mode']}")
print(f"✓ Risk model: {config['risk']['model']}")
```

**Expected**: No errors, prints symbol/mode/model

---

### 2. Fallback CSV Load Test
**Purpose**: Verify data_feed can load CSV data

```python
import data_feed

config = {
    "time": {
        "data_timezone": "broker",
        "system_timezone": "UTC"
    }
}

df = data_feed.get_csv_ohlcv("data/fallback.csv", config)
print(f"✓ Loaded {len(df)} bars from CSV")
print(f"✓ Columns: {list(df.columns)}")
print(f"✓ Time range: {df['time'].min()} to {df['time'].max()}")
```

**Expected**: Loads data, shows bar count, valid time range

---

### 3. Strategy Output Validation Test
**Purpose**: Verify strategy generates valid signals and validator catches issues

```python
import pandas as pd
import yaml
from pathlib import Path
import strategy
import validator

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Load data
import data_feed
df = data_feed.get_csv_ohlcv("data/fallback.csv", config)

# Generate signals
signals = strategy.generate_signals(df, config)
print(f"✓ Generated {len(signals)} signal rows")
print(f"✓ Signals: {(signals['signal'] != 0).sum()} non-zero")

# Validate
valid, errors = validator.validate_strategy_output(df, signals)
if valid:
    print("✓ Validation passed")
else:
    print(f"✗ Validation failed: {errors}")
```

**Expected**: Signals generated, validation passes

---

### 4. Backtest Engine Test
**Purpose**: Verify backtest runs without crashing

```python
import yaml
import data_feed
import strategy
import backtest_engine

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Get data and signals
df = data_feed.get_csv_ohlcv("data/fallback.csv", config)
signals = strategy.generate_signals(df, config)

# Run backtest
result = backtest_engine.run_backtest(signals, config,