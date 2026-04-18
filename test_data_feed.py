"""
Test script for data_feed.py - demonstrates expected output format
"""

import yaml
from data_feed import get_ohlcv, is_mt5_available

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Test MT5 availability
print("=" * 60)
print("MT5 AVAILABILITY TEST")
print("=" * 60)
mt5_status = is_mt5_available()
print(f"MT5 Available: {mt5_status}")
print()

# Test data loading
print("=" * 60)
print("DATA LOADING TEST")
print("=" * 60)
try:
    df = get_ohlcv(
        symbol=config["backtest"]["symbol"],
        timeframe=config["backtest"]["timeframe"],
        start_date=config["windows"]["train_start"],
        end_date=config["windows"]["train_end"],
        config=config
    )
    
    print(f"\nSuccessfully loaded data!")
    print(f"Shape: {df.shape}")
    print(f"\nColumns and dtypes:")
    print(df.dtypes)
    print(f"\nFirst 5 rows:")
    print(df.head())
    print(f"\nLast 5 rows:")
    print(df.tail())
    print(f"\nTimestamp timezone: {df['time'].dt.tz}")
    print(f"\nData range:")
    print(f"  Start: {df['time'].min()}")
    print(f"  End:   {df['time'].max()}")
    print(f"\nBasic stats:")
    print(df.describe())
    
except Exception as e:
    print(f"Error loading  {e}")
    import traceback
    traceback.print_exc()
