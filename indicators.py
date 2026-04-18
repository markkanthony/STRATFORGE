"""
StratForge - Indicator Library

Standalone pure functions. Each accepts a DataFrame with standard OHLCV columns
(open, high, low, close, tick_volume) and returns a pd.Series aligned to the
same index.

Designed to be used as lambdas in ComposableStrategy:

    from indicators import ema, atr, rsi

    strategy.add_indicator("ema_fast", lambda df: ema(df, 10))
    strategy.add_indicator("atr",      lambda df: atr(df, 14))

All functions use only past data — no lookahead.
EWM functions use adjust=False (Wilder/recursive smoothing).
"""

import pandas as pd
import numpy as np


# ------------------------------------------------------------------ #
# Trend / moving averages                                              #
# ------------------------------------------------------------------ #

def ema(df: pd.DataFrame, period: int) -> pd.Series:
    """Exponential moving average of close."""
    return df["close"].ewm(span=period, adjust=False).mean()


def sma(df: pd.DataFrame, period: int) -> pd.Series:
    """Simple moving average of close."""
    return df["close"].rolling(window=period, min_periods=1).mean()


def wma(df: pd.DataFrame, period: int) -> pd.Series:
    """Weighted moving average of close (linearly weighted)."""
    weights = np.arange(1, period + 1, dtype=float)
    return df["close"].rolling(window=period, min_periods=1).apply(
        lambda x: np.dot(x[-len(weights):], weights[-len(x):]) / weights[-len(x):].sum(),
        raw=True,
    )


# ------------------------------------------------------------------ #
# Momentum                                                             #
# ------------------------------------------------------------------ #

def rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Relative Strength Index using Wilder smoothing (EWM com = period-1).
    Returns values in [0, 100]. First bar defaults to 50 (neutral).
    """
    delta = df["close"].diff(1)
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    result = 100.0 - (100.0 / (1.0 + rs))
    return result.fillna(50.0)


def macd_line(df: pd.DataFrame, fast: int = 12, slow: int = 26) -> pd.Series:
    """MACD line = EMA(fast) - EMA(slow)."""
    return (
        df["close"].ewm(span=fast, adjust=False).mean()
        - df["close"].ewm(span=slow, adjust=False).mean()
    )


def macd_signal(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    """MACD signal line = EMA(macd_line, signal)."""
    line = macd_line(df, fast, slow)
    return line.ewm(span=signal, adjust=False).mean()


def macd_histogram(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    """MACD histogram = macd_line - macd_signal."""
    line = macd_line(df, fast, slow)
    sig = line.ewm(span=signal, adjust=False).mean()
    return line - sig


def stochastic_k(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Stochastic %K. Values in [0, 100]."""
    lowest_low  = df["low"].rolling(window=period, min_periods=1).min()
    highest_high = df["high"].rolling(window=period, min_periods=1).max()
    denom = (highest_high - lowest_low).replace(0.0, np.nan)
    return ((df["close"] - lowest_low) / denom * 100.0).fillna(50.0)


def stochastic_d(df: pd.DataFrame, period: int = 14, smooth: int = 3) -> pd.Series:
    """Stochastic %D = SMA(K, smooth)."""
    k = stochastic_k(df, period)
    return k.rolling(window=smooth, min_periods=1).mean()


# ------------------------------------------------------------------ #
# Volatility                                                           #
# ------------------------------------------------------------------ #

def true_range(df: pd.DataFrame) -> pd.Series:
    """True Range = max(H-L, |H-prev_close|, |L-prev_close|)."""
    prev_close = df["close"].shift(1)
    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"]  - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range using Wilder smoothing."""
    tr = true_range(df)
    return tr.ewm(com=period - 1, adjust=False).mean()


def bollinger_upper(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.Series:
    """Bollinger upper band."""
    mid = df["close"].rolling(window=period, min_periods=1).mean()
    sigma = df["close"].rolling(window=period, min_periods=1).std(ddof=0).fillna(0.0)
    return mid + std * sigma


def bollinger_lower(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.Series:
    """Bollinger lower band."""
    mid = df["close"].rolling(window=period, min_periods=1).mean()
    sigma = df["close"].rolling(window=period, min_periods=1).std(ddof=0).fillna(0.0)
    return mid - std * sigma


def bollinger_mid(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Bollinger middle band (SMA)."""
    return df["close"].rolling(window=period, min_periods=1).mean()


def bollinger_width(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.Series:
    """Bollinger Band Width = (upper - lower) / mid."""
    mid = bollinger_mid(df, period)
    upper = bollinger_upper(df, period, std)
    lower = bollinger_lower(df, period, std)
    return (upper - lower) / mid.replace(0.0, np.nan)


# ------------------------------------------------------------------ #
# Volume                                                               #
# ------------------------------------------------------------------ #

def volume_sma(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Simple moving average of tick volume."""
    return df["tick_volume"].rolling(window=period, min_periods=1).mean()


def relative_volume(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Current volume relative to its SMA (1.0 = average)."""
    avg = volume_sma(df, period)
    return df["tick_volume"] / avg.replace(0.0, np.nan)


# ------------------------------------------------------------------ #
# Price levels / structure                                             #
# ------------------------------------------------------------------ #

def highest_high(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Rolling highest high over N bars (inclusive of current bar)."""
    return df["high"].rolling(window=period, min_periods=1).max()


def lowest_low(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Rolling lowest low over N bars (inclusive of current bar)."""
    return df["low"].rolling(window=period, min_periods=1).min()


def donchian_upper(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Donchian channel upper = highest high over N bars."""
    return highest_high(df, period)


def donchian_lower(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Donchian channel lower = lowest low over N bars."""
    return lowest_low(df, period)
