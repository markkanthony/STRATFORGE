"""
StratForge - Data Feed Module

This module handles market data loading from MetaTrader5 and CSV fallback.
All timestamps are normalized to UTC internally.

PURPOSE:
Build a robust market data loader with:
- MetaTrader5 fetch support
- CSV fallback support
- timezone normalization

REQUIREMENTS:
- Handle MT5 initialize and shutdown safely
- Use UTC internally as system timezone
- All timestamps must be tz-aware inside the program
- If raw data is broker time, localize first, then convert to UTC
- Standardize columns: time, open, high, low, close, tick_volume
- Sort ascending
- Drop duplicates by timestamp
- Validate non-empty data
- Return a pandas DataFrame
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

import pandas as pd
import pytz

# Try to import MetaTrader5 - it may not be available on all systems
MT5_AVAILABLE = False
MT5 = None
try:
    import MetaTrader5 as MT5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False


# Timeframe mapping from config string to MT5 constants
TIMEFRAME_MAP = {
    "M1": 1,      # MT5.TIMEFRAME_M1
    "M5": 5,      # MT5.TIMEFRAME_M5
    "M15": 15,    # MT5.TIMEFRAME_M15
    "M30": 30,    # MT5.TIMEFRAME_M30
    "H1": 16385,  # MT5.TIMEFRAME_H1
    "H4": 16388,  # MT5.TIMEFRAME_H4
    "D1": 16408,  # MT5.TIMEFRAME_D1
    "W1": 32769,  # MT5.TIMEFRAME_W1
    "MN1": 49153, # MT5.TIMEFRAME_MN1
}


def is_mt5_available() -> bool:
    """
    Check if MetaTrader5 is available and can be initialized.
    
    Returns:
        bool: True if MT5 is available and can be initialized, False otherwise
    """
    if not MT5_AVAILABLE:
        return False
    
    # Try to initialize MT5
    try:
        if not MT5.initialize():
            return False
        MT5.shutdown()
        return True
    except Exception:
        return False


def resolve_symbol(symbol: str) -> str:
    """
    Resolve symbol name for MT5.
    Some brokers use suffixes like ".raw" or "m" - this function handles normalization.
    
    Args:
        symbol: Base symbol name (e.g., "EURUSD")
    
    Returns:
        str: Resolved symbol name that should work with the broker
    
    Note:
        This is a simple implementation. In production, you might want to:
        - Try multiple suffix variations
        - Query available symbols from MT5
        - Use a broker-specific mapping
    """
    # For now, return the symbol as-is
    # In the future, this could check MT5.symbols_get() and try variations
    return symbol


def _parse_timeframe(timeframe_str: str) -> int:
    """
    Convert timeframe string to MT5 timeframe constant.
    
    Args:
        timeframe_str: Timeframe string like "H1", "M5", "D1"
    
    Returns:
        int: MT5 timeframe constant
    
    Raises:
        ValueError: If timeframe string is not recognized
    """
    tf_upper = timeframe_str.upper()
    if tf_upper not in TIMEFRAME_MAP:
        raise ValueError(
            f"Unrecognized timeframe: {timeframe_str}. "
            f"Supported: {', '.join(TIMEFRAME_MAP.keys())}"
        )
    return TIMEFRAME_MAP[tf_upper]


def _normalize_timestamps(
    df: pd.DataFrame,
    source_timezone: str,
    time_column: str = "time"
) -> pd.DataFrame:
    """
    Normalize timestamps to UTC timezone-aware datetimes.
    
    Args:
        df: DataFrame with time column
        source_timezone: Source timezone (e.g., "broker", "UTC", "Asia/Manila")
        time_column: Name of the time column
    
    Returns:
        pd.DataFrame: DataFrame with normalized UTC timestamps
    """
    if df.empty:
        return df
    
    # Make a copy to avoid modifying original
    df = df.copy()
    
    # If source_timezone is "broker", assume it's already UTC
    # (This is a simplification; in production you'd need broker-specific logic)
    if source_timezone.lower() == "broker":
        source_timezone = "UTC"
    
    # Parse timezone
    try:
        tz = pytz.timezone(source_timezone)
    except Exception:
        print(f"Warning: Invalid timezone '{source_timezone}', defaulting to UTC")
        tz = pytz.UTC
    
    # Ensure time column is datetime
    if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
        df[time_column] = pd.to_datetime(df[time_column])
    
    # If already timezone-aware, convert to UTC
    if df[time_column].dt.tz is not None:
        df[time_column] = df[time_column].dt.tz_convert(pytz.UTC)
    else:
        # Localize to source timezone, then convert to UTC
        df[time_column] = df[time_column].dt.tz_localize(tz).dt.tz_convert(pytz.UTC)
    
    return df


def get_mt5_ohlcv(
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    config: dict
) -> pd.DataFrame:
    """
    Fetch OHLCV data from MetaTrader5.
    
    Args:
        symbol: Trading symbol (e.g., "EURUSD")
        timeframe: Timeframe string (e.g., "H1")
        start_date: Start date string (e.g., "2023-01-01")
        end_date: End date string (e.g., "2023-12-31")
        config: Configuration dictionary containing timezone settings
    
    Returns:
        pd.DataFrame: OHLCV data with columns:
            time, open, high, low, close, tick_volume
    
    Raises:
        RuntimeError: If MT5 is not available or initialization fails
        ValueError: If no data is returned
    """
    if not MT5_AVAILABLE:
        raise RuntimeError(
            "MetaTrader5 is not available. Install it with: pip install MetaTrader5"
        )
    
    # Initialize MT5
    if not MT5.initialize():
        error_code = MT5.last_error()
        raise RuntimeError(f"MT5 initialization failed: {error_code}")
    
    try:
        # Resolve symbol
        resolved_symbol = resolve_symbol(symbol)
        
        # Parse timeframe
        mt5_timeframe = _parse_timeframe(timeframe)
        
        # Parse dates
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Fetch data
        rates = MT5.copy_rates_range(
            resolved_symbol,
            mt5_timeframe,
            start_dt,
            end_dt
        )
        
        if rates is None or len(rates) == 0:
            raise ValueError(
                f"No data returned from MT5 for {resolved_symbol} {timeframe} "
                f"from {start_date} to {end_date}"
            )
        
        # Convert to DataFrame
        df = pd.DataFrame(rates)
        
        # MT5 returns time as Unix timestamp - convert to datetime
        df["time"] = pd.to_datetime(df["time"], unit="s")
        
        # Standardize columns
        df = df[["time", "open", "high", "low", "close", "tick_volume"]]
        
        # Normalize timestamps to UTC
        # MT5 typically returns broker time, which we'll convert to UTC
        data_timezone = config.get("time", {}).get("data_timezone", "broker")
        df = _normalize_timestamps(df, data_timezone, "time")
        
        # Sort by time ascending
        df = df.sort_values("time").reset_index(drop=True)
        
        # Drop duplicates
        df = df.drop_duplicates(subset=["time"], keep="first")
        
        # Validate non-empty
        if df.empty:
            raise ValueError("Data is empty after processing")
        
        return df
        
    finally:
        # Always shutdown MT5
        MT5.shutdown()


def get_csv_ohlcv(path: str, config: dict) -> pd.DataFrame:
    """
    Load OHLCV data from CSV file.
    
    Args:
        path: Path to CSV file (relative or absolute)
        config: Configuration dictionary containing timezone settings
    
    Returns:
        pd.DataFrame: OHLCV data with columns:
            time, open, high, low, close, tick_volume
    
    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV doesn't have required columns or is empty
    """
    csv_path = Path(path)
    
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    # Read CSV
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        raise ValueError(f"Failed to read CSV file: {e}")
    
    # Check required columns
    required_cols = ["time", "open", "high", "low", "close"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        raise ValueError(
            f"CSV missing required columns: {missing_cols}. "
            f"Available columns: {list(df.columns)}"
        )
    
    # Add tick_volume if missing (set to 0)
    if "tick_volume" not in df.columns:
        df["tick_volume"] = 0
    
    # Select and order columns
    df = df[["time", "open", "high", "low", "close", "tick_volume"]].copy()
    
    # Parse time column
    try:
        df["time"] = pd.to_datetime(df["time"])
    except Exception as e:
        raise ValueError(f"Failed to parse time column: {e}")
    
    # Normalize timestamps to UTC
    data_timezone = config.get("time", {}).get("data_timezone", "broker")
    df = _normalize_timestamps(df, data_timezone, "time")
    
    # Sort by time ascending
    df = df.sort_values("time").reset_index(drop=True)
    
    # Drop duplicates
    df = df.drop_duplicates(subset=["time"], keep="first")
    
    # Validate non-empty
    if df.empty:
        raise ValueError("CSV data is empty after processing")
    
    return df


def get_ohlcv(
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    config: dict
) -> pd.DataFrame:
    """
    Get OHLCV data - tries MT5 first, falls back to CSV.
    
    This is the main entry point for fetching market data.
    
    Args:
        symbol: Trading symbol (e.g., "EURUSD")
        timeframe: Timeframe string (e.g., "H1")
        start_date: Start date string (e.g., "2023-01-01")
        end_date: End date string (e.g., "2023-12-31")
        config: Configuration dictionary containing timezone settings
    
    Returns:
        pd.DataFrame: OHLCV data with columns:
            time, open, high, low, close, tick_volume
        
        All timestamps are UTC timezone-aware.
    
    Raises:
        ValueError: If no data source is available or data is invalid
    """
    # Try MT5 first if available
    if is_mt5_available():
        try:
            print(f"Fetching {symbol} {timeframe} data from MT5...")
            df = get_mt5_ohlcv(symbol, timeframe, start_date, end_date, config)
            print(f"Successfully fetched {len(df)} bars from MT5")
            return df
        except Exception as e:
            print(f"MT5 fetch failed: {e}")
            print("Falling back to CSV...")
    else:
        print("MT5 not available, using CSV fallback...")
    
    # Fall back to CSV
    csv_path = Path("data") / "fallback.csv"
    
    try:
        df = get_csv_ohlcv(str(csv_path), config)
        print(f"Successfully loaded {len(df)} bars from CSV: {csv_path}")
        
        # Filter to requested date range
        start_dt = pd.Timestamp(start_date, tz=pytz.UTC)
        end_dt = pd.Timestamp(end_date, tz=pytz.UTC)
        
        df = df[(df["time"] >= start_dt) & (df["time"] <= end_dt)].copy()
        
        if df.empty:
            raise ValueError(
                f"No data available in CSV for date range {start_date} to {end_date}"
            )
        
        print(f"Filtered to {len(df)} bars in requested date range")
        return df
        
    except Exception as e:
        raise ValueError(f"Failed to load data from CSV: {e}")