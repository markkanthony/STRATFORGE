"""
StratForge - Pattern Library

Standalone pure functions. Each accepts a DataFrame with standard OHLCV columns
and returns a boolean pd.Series aligned to the same index.

Designed to be used as lambdas in ComposableStrategy:

    from patterns import bullish_engulfing, sweep_prev_low

    strategy.add_pattern("bullish_engulfing", bullish_engulfing)
    strategy.add_pattern("sweep_prev_low",    sweep_prev_low)

ORB patterns require a period argument — wrap in a lambda:

    strategy.add_pattern("orb_long", lambda df: orb_breakout_long(df, bars=3))

NO-LOOKAHEAD GUARANTEE:
All patterns use shift(1) to reference the prior bar only. The current bar's
OHLCV is allowed (it is the bar being evaluated). No future bar data is used.
"""

import pandas as pd
import numpy as np


# ------------------------------------------------------------------ #
# Candlestick patterns                                                 #
# ------------------------------------------------------------------ #

def bullish_engulfing(df: pd.DataFrame) -> pd.Series:
    """
    Bullish engulfing: prior bar is bearish, current bar is bullish,
    current body fully engulfs prior body.
    """
    prev_open  = df["open"].shift(1)
    prev_close = df["close"].shift(1)
    prev_bearish   = prev_open > prev_close
    curr_bullish   = df["close"] > df["open"]
    body_engulfs   = (df["open"] <= prev_close) & (df["close"] >= prev_open)
    return (prev_bearish & curr_bullish & body_engulfs).fillna(False)


def bearish_engulfing(df: pd.DataFrame) -> pd.Series:
    """
    Bearish engulfing: prior bar is bullish, current bar is bearish,
    current body fully engulfs prior body.
    """
    prev_open  = df["open"].shift(1)
    prev_close = df["close"].shift(1)
    prev_bullish   = prev_open < prev_close
    curr_bearish   = df["close"] < df["open"]
    body_engulfs   = (df["open"] >= prev_close) & (df["close"] <= prev_open)
    return (prev_bullish & curr_bearish & body_engulfs).fillna(False)


def bullish_pin_bar(df: pd.DataFrame, wick_ratio: float = 2.0) -> pd.Series:
    """
    Bullish pin bar (hammer): lower wick at least `wick_ratio` times the body,
    upper wick small, close in upper half of range.
    """
    body       = (df["close"] - df["open"]).abs()
    lower_wick = df[["open", "close"]].min(axis=1) - df["low"]
    upper_wick = df["high"] - df[["open", "close"]].max(axis=1)
    bar_range  = df["high"] - df["low"]
    close_upper_half = df["close"] > (df["high"] + df["low"]) / 2.0
    long_lower = lower_wick >= wick_ratio * body.replace(0.0, np.nan).fillna(1e-10)
    short_upper = upper_wick <= body.replace(0.0, np.nan).fillna(1e-10)
    return (long_lower & short_upper & close_upper_half & (bar_range > 0)).fillna(False)


def bearish_pin_bar(df: pd.DataFrame, wick_ratio: float = 2.0) -> pd.Series:
    """
    Bearish pin bar (shooting star): upper wick at least `wick_ratio` times
    the body, lower wick small, close in lower half of range.
    """
    body       = (df["close"] - df["open"]).abs()
    upper_wick = df["high"] - df[["open", "close"]].max(axis=1)
    lower_wick = df[["open", "close"]].min(axis=1) - df["low"]
    bar_range  = df["high"] - df["low"]
    close_lower_half = df["close"] < (df["high"] + df["low"]) / 2.0
    long_upper  = upper_wick >= wick_ratio * body.replace(0.0, np.nan).fillna(1e-10)
    short_lower = lower_wick <= body.replace(0.0, np.nan).fillna(1e-10)
    return (long_upper & short_lower & close_lower_half & (bar_range > 0)).fillna(False)


def doji(df: pd.DataFrame, threshold: float = 0.1) -> pd.Series:
    """
    Doji: body is less than `threshold` fraction of the total bar range.
    """
    body      = (df["close"] - df["open"]).abs()
    bar_range = (df["high"] - df["low"]).replace(0.0, np.nan)
    return (body / bar_range <= threshold).fillna(False)


# ------------------------------------------------------------------ #
# Structure patterns                                                   #
# ------------------------------------------------------------------ #

def inside_bar(df: pd.DataFrame) -> pd.Series:
    """
    Inside bar: current bar's high < prior bar's high AND
    current bar's low > prior bar's low.
    """
    prev_high = df["high"].shift(1)
    prev_low  = df["low"].shift(1)
    return ((df["high"] < prev_high) & (df["low"] > prev_low)).fillna(False)


def outside_bar(df: pd.DataFrame) -> pd.Series:
    """
    Outside bar (engulfing range): current bar's high > prior high AND
    current bar's low < prior low.
    """
    prev_high = df["high"].shift(1)
    prev_low  = df["low"].shift(1)
    return ((df["high"] > prev_high) & (df["low"] < prev_low)).fillna(False)


# ------------------------------------------------------------------ #
# Sweep / liquidity grab patterns                                      #
# ------------------------------------------------------------------ #

def sweep_prev_high(df: pd.DataFrame) -> pd.Series:
    """
    Bearish sweep of prior high: bar wicks above prior bar's high but
    closes back below it (stop-hunt / liquidity grab at prior high).
    """
    prev_high = df["high"].shift(1)
    return ((df["high"] > prev_high) & (df["close"] < prev_high)).fillna(False)


def sweep_prev_low(df: pd.DataFrame) -> pd.Series:
    """
    Bullish sweep of prior low: bar wicks below prior bar's low but
    closes back above it (stop-hunt / liquidity grab at prior low).
    """
    prev_low = df["low"].shift(1)
    return ((df["low"] < prev_low) & (df["close"] > prev_low)).fillna(False)


def break_above_prev_high(df: pd.DataFrame) -> pd.Series:
    """Close above prior bar's high (clean bullish breakout)."""
    return (df["close"] > df["high"].shift(1)).fillna(False)


def break_below_prev_low(df: pd.DataFrame) -> pd.Series:
    """Close below prior bar's low (clean bearish breakout)."""
    return (df["close"] < df["low"].shift(1)).fillna(False)


# ------------------------------------------------------------------ #
# Opening Range Breakout                                               #
# ------------------------------------------------------------------ #

def orb_breakout_long(df: pd.DataFrame, bars: int = 3) -> pd.Series:
    """
    Bullish ORB breakout: close above the high of the first `bars` bars
    of each trading day.

    Returns False for bars that are still within the opening range window.
    """
    return _orb_signal(df, bars, direction="long")


def orb_breakout_short(df: pd.DataFrame, bars: int = 3) -> pd.Series:
    """
    Bearish ORB breakout: close below the low of the first `bars` bars
    of each trading day.
    """
    return _orb_signal(df, bars, direction="short")


def _orb_signal(df: pd.DataFrame, bars: int, direction: str) -> pd.Series:
    """Internal helper for ORB calculations."""
    tmp = df.copy()
    tmp["_date"] = tmp["time"].dt.date
    tmp["_bar_of_day"] = tmp.groupby("_date").cumcount()

    is_orb = tmp["_bar_of_day"] < bars

    if direction == "long":
        orb_levels = tmp.loc[is_orb].groupby("_date")["high"].max()
        level_col = tmp["_date"].map(orb_levels)
        signal = (
            (tmp["_bar_of_day"] >= bars)
            & level_col.notna()
            & (tmp["close"] > level_col)
        )
    else:
        orb_levels = tmp.loc[is_orb].groupby("_date")["low"].min()
        level_col = tmp["_date"].map(orb_levels)
        signal = (
            (tmp["_bar_of_day"] >= bars)
            & level_col.notna()
            & (tmp["close"] < level_col)
        )

    return signal.fillna(False).values  # return as plain array for alignment safety


# ------------------------------------------------------------------ #
# Rolling structure                                                    #
# ------------------------------------------------------------------ #

def higher_high(df: pd.DataFrame, lookback: int = 3) -> pd.Series:
    """
    Current high is the highest in the last `lookback` bars (including current).
    Useful for identifying local swing highs.
    """
    return (df["high"] == df["high"].rolling(window=lookback, min_periods=lookback).max()).fillna(False)


def lower_low(df: pd.DataFrame, lookback: int = 3) -> pd.Series:
    """Current low is the lowest in the last `lookback` bars."""
    return (df["low"] == df["low"].rolling(window=lookback, min_periods=lookback).min()).fillna(False)
