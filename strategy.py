"""
StratForge - Strategy Module

Generates trading signals from OHLCV data.
Supports indicator-driven, pattern-driven, and hybrid modes.

PIPELINE ORDER:
  generate_signals
    -> build_indicator_features   (EMA, RSI, ATR)
    -> build_pattern_features     (engulfing, inside bar, sweeps, ORB)
    -> build_context_features     (trend, prev-day levels, session)
    -> evaluate_rules             (config-driven signal column)
    -> build_exit_levels          (ATR-based SL/TP)

NO-LOOKAHEAD GUARANTEE:
- All pattern features use shift(1) to reference prior-bar data only.
- EMA values at bar i incorporate bar i's close (EWM by definition), which is
  acceptable because signals are executed on bar i+1 open (next-bar-open logic).
- Trend direction (trend_up/trend_down) additionally shifts EMA by 1 to use
  the confirmed prior-bar EMA state — conservative, safe choice.
- ATR uses close.shift(1) for True Range calculation (standard).
- ORB levels are built from bars within the same day that precede the current bar;
  the range is forward-filled, never backward-filled.
- Previous-day H/L uses a daily groupby that is shifted 1 day before merging back.
"""

from typing import Dict
import pandas as pd
import numpy as np


# ------------------------------------------------------------------ #
# Public entry point                                                   #
# ------------------------------------------------------------------ #

def generate_signals(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    Generate trading signals from OHLCV data.

    Args:
        df: DataFrame with columns time, open, high, low, close, tick_volume.
            Timestamps must be tz-aware UTC (as produced by data_feed.py).
        config: Full config dict.

    Returns:
        Copy of df with added columns:
            signal    int  {-1, 0, 1}
            sl_price  float | NaN
            tp_price  float | NaN
        Plus boolean feature columns referenced by entry rules.
    """
    mode = config["strategy"].get("mode", "hybrid")
    df = df.copy()

    if mode in ("indicator", "hybrid"):
        df = build_indicator_features(df, config)

    if mode in ("pattern", "hybrid"):
        df = build_pattern_features(df, config)

    # Context features always run (provides trend_up/down and session column
    # which backtest_engine accesses on every bar regardless of mode).
    df = build_context_features(df, config)

    # In pure pattern mode, trend columns from indicators may be absent;
    # ensure they exist as False so rule evaluation doesn't KeyError.
    if mode == "pattern":
        for col in ("ema_fast", "ema_slow", "rsi", "atr", "tr"):
            if col not in df.columns:
                df[col] = np.nan
        if "trend_up" not in df.columns:
            df["trend_up"] = False
        if "trend_down" not in df.columns:
            df["trend_down"] = False

    # In pure indicator mode, pattern boolean columns may be absent.
    if mode == "indicator":
        _ensure_pattern_columns_false(df)

    df = evaluate_rules(df, config)
    df = build_exit_levels(df, config)

    # Final guarantees for downstream consumers
    df["signal"] = df["signal"].fillna(0).astype(int)
    if "sl_price" not in df.columns:
        df["sl_price"] = np.nan
    if "tp_price" not in df.columns:
        df["tp_price"] = np.nan

    return df


# ------------------------------------------------------------------ #
# Indicator features                                                   #
# ------------------------------------------------------------------ #

def build_indicator_features(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """Add EMA fast/slow, RSI, and ATR columns."""
    ind_cfg = config["strategy"].get("indicators", {})
    fast_period = int(ind_cfg.get("fast_ema", 10))
    slow_period = int(ind_cfg.get("slow_ema", 50))
    rsi_period = int(ind_cfg.get("rsi_period", 14))
    atr_period = int(ind_cfg.get("atr_period", 14))

    close = df["close"]
    high = df["high"]
    low = df["low"]

    # EMA — ewm with adjust=False uses recursive (Wilder-style) smoothing
    df["ema_fast"] = close.ewm(span=fast_period, adjust=False).mean()
    df["ema_slow"] = close.ewm(span=slow_period, adjust=False).mean()

    # RSI — Wilder smoothing (com = period - 1)
    delta = close.diff(1)
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(com=rsi_period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=rsi_period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    df["rsi"] = 100.0 - (100.0 / (1.0 + rs))
    df["rsi"] = df["rsi"].fillna(50.0)  # neutral default for first bar

    # ATR — True Range then Wilder EMA
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    df["tr"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["atr"] = df["tr"].ewm(com=atr_period - 1, adjust=False).mean()

    return df


# ------------------------------------------------------------------ #
# Pattern features                                                     #
# ------------------------------------------------------------------ #

def build_pattern_features(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    Add boolean pattern columns.
    Disabled patterns are created as False columns so rule evaluation
    never raises KeyError.
    """
    pat_cfg = config["strategy"].get("patterns", {})

    prev_open = df["open"].shift(1)
    prev_close = df["close"].shift(1)
    prev_high = df["high"].shift(1)
    prev_low = df["low"].shift(1)

    # ---- Engulfing patterns ---------------------------------------- #
    if pat_cfg.get("bullish_engulfing", False):
        prev_bearish = prev_open > prev_close
        curr_bullish = df["close"] > df["open"]
        body_engulfs = (df["open"] <= prev_close) & (df["close"] >= prev_open)
        df["bullish_engulfing"] = prev_bearish & curr_bullish & body_engulfs
    else:
        df["bullish_engulfing"] = False

    if pat_cfg.get("bearish_engulfing", False):
        prev_bullish = prev_open < prev_close
        curr_bearish = df["close"] < df["open"]
        body_engulfs = (df["open"] >= prev_close) & (df["close"] <= prev_open)
        df["bearish_engulfing"] = prev_bullish & curr_bearish & body_engulfs
    else:
        df["bearish_engulfing"] = False

    # ---- Inside bar ------------------------------------------------ #
    if pat_cfg.get("inside_bar_breakout", False):
        df["inside_bar"] = (df["high"] < prev_high) & (df["low"] > prev_low)
    else:
        df["inside_bar"] = False

    # ---- Sweep patterns ------------------------------------------- #
    # Sweep prev high: bar briefly exceeds prior high but closes below it
    # (bearish rejection / stop hunt of prior high)
    if pat_cfg.get("sweep_prev_high", False):
        df["sweep_prev_high"] = (df["high"] > prev_high) & (df["close"] < prev_high)
    else:
        df["sweep_prev_high"] = False

    # Sweep prev low: bar briefly dips below prior low but closes above it
    # (bullish rejection / stop hunt of prior low)
    if pat_cfg.get("sweep_prev_low", False):
        df["sweep_prev_low"] = (df["low"] < prev_low) & (df["close"] > prev_low)
    else:
        df["sweep_prev_low"] = False

    # ---- Opening Range Breakout ------------------------------------ #
    orb_cfg = pat_cfg.get("orb", {})
    if orb_cfg.get("enabled", False):
        df = _build_orb_features(df, int(orb_cfg.get("bars", 3)))
    else:
        df["orb_high"] = np.nan
        df["orb_low"] = np.nan
        df["orb_breakout_long"] = False
        df["orb_breakout_short"] = False

    return df


def _build_orb_features(df: pd.DataFrame, orb_bars: int) -> pd.DataFrame:
    """
    Compute Opening Range Breakout levels and breakout flags.

    For each trading day, the ORB range is the high/low of the first
    `orb_bars` bars. This range is forward-filled to subsequent bars
    of the same day. No backward filling is performed.
    """
    # Extract date from tz-aware timestamp
    dates = df["time"].dt.date
    df = df.copy()
    df["_date"] = dates
    df["_bar_of_day"] = df.groupby("_date").cumcount()

    # Identify ORB bars (strictly before index orb_bars within day)
    is_orb = df["_bar_of_day"] < orb_bars

    # Per-day ORB high and low from the ORB window bars only
    orb_highs = df.loc[is_orb].groupby("_date")["high"].max()
    orb_lows = df.loc[is_orb].groupby("_date")["low"].min()

    df["orb_high"] = df["_date"].map(orb_highs)
    df["orb_low"] = df["_date"].map(orb_lows)

    # Breakout only valid after ORB window is complete
    after_orb = df["_bar_of_day"] >= orb_bars
    df["orb_breakout_long"] = (
        after_orb & df["orb_high"].notna() & (df["close"] > df["orb_high"])
    )
    df["orb_breakout_short"] = (
        after_orb & df["orb_low"].notna() & (df["close"] < df["orb_low"])
    )

    # ORB bars themselves get NaN levels (range not yet confirmed)
    df.loc[is_orb, ["orb_high", "orb_low"]] = np.nan
    df.loc[is_orb, ["orb_breakout_long", "orb_breakout_short"]] = False

    df.drop(columns=["_date", "_bar_of_day"], inplace=True)
    return df


# ------------------------------------------------------------------ #
# Context features                                                     #
# ------------------------------------------------------------------ #

def build_context_features(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    Add trend direction, previous-day H/L, and session columns.

    trend_up / trend_down use ema_fast.shift(1) > ema_slow.shift(1) so that
    the trend state used for a bar's signal is based on the EMA as of the
    *prior* bar close — the most conservative no-lookahead choice.
    """
    ctx_cfg = config["strategy"].get("context", {})

    # ---- Trend filter --------------------------------------------- #
    trend_filter = ctx_cfg.get("trend_filter", "ema")
    if trend_filter == "ema" and "ema_fast" in df.columns and "ema_slow" in df.columns:
        prev_fast = df["ema_fast"].shift(1)
        prev_slow = df["ema_slow"].shift(1)
        df["trend_up"] = (prev_fast > prev_slow).fillna(False)
        df["trend_down"] = (prev_fast < prev_slow).fillna(False)
    else:
        df["trend_up"] = False
        df["trend_down"] = False

    # ---- Previous day high / low ---------------------------------- #
    if ctx_cfg.get("use_prev_day_levels", False):
        df = _build_prev_day_levels(df)
    else:
        df["prev_day_high"] = np.nan
        df["prev_day_low"] = np.nan

    # ---- Session label ------------------------------------------- #
    # Always produces the 'session' column (backtest_engine reads it on
    # every signal bar via signal_bar.get('session', 'unknown')).
    if ctx_cfg.get("use_session_filter", False):
        df = _build_session_column(df, config)
    else:
        df["session"] = "all"

    return df


def _build_prev_day_levels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute previous trading day's high and low for each bar.

    Approach: group by UTC date, get daily H/L, shift 1 day,
    then map back to the intraday bars.
    """
    df = df.copy()
    df["_date"] = df["time"].dt.date

    daily = (
        df.groupby("_date")
        .agg(day_high=("high", "max"), day_low=("low", "min"))
        .reset_index()
        .sort_values("_date")
    )

    daily["prev_day_high"] = daily["day_high"].shift(1)
    daily["prev_day_low"] = daily["day_low"].shift(1)
    daily = daily[["_date", "prev_day_high", "prev_day_low"]]

    df = df.merge(daily, on="_date", how="left")
    df.drop(columns=["_date"], inplace=True)
    return df


def _build_session_column(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    Label each bar with its primary trading session based on UTC hour.

    Sessions (UTC):
        overlap : 12–16  (London / New York overlap — highest liquidity)
        london  : 07–16
        newyork : 12–21
        asia    : 00–08
        off     : everything else
    """
    hour = df["time"].dt.hour

    session = pd.Series("off", index=df.index)
    session = session.where(~((hour >= 0) & (hour < 8)), other="asia")
    session = session.where(~((hour >= 7) & (hour < 16)), other="london")
    session = session.where(~((hour >= 12) & (hour < 21)), other="newyork")
    # Overlap overrides both london and newyork
    session = session.where(~((hour >= 12) & (hour < 16)), other="overlap")

    df["session"] = session
    return df


# ------------------------------------------------------------------ #
# Rule evaluation                                                      #
# ------------------------------------------------------------------ #

def evaluate_rules(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    Produce signal column from config-driven boolean AND rules.

    Reads entry.long_require_all and entry.short_require_all lists.
    Each list item is a column name in df that must be True (truthy) for
    the respective signal to fire.

    Mutual exclusion: if both long and short conditions are simultaneously
    true (degenerate case), signal is set to 0.
    """
    entry_cfg = config["strategy"].get("entry", {})
    long_rules = entry_cfg.get("long_require_all", [])
    short_rules = entry_cfg.get("short_require_all", [])

    long_mask = _build_rule_mask(df, long_rules)
    short_mask = _build_rule_mask(df, short_rules)

    df["signal"] = 0
    df.loc[long_mask, "signal"] = 1
    df.loc[short_mask, "signal"] = -1
    # Conflict resolution: both conditions met → no signal
    df.loc[long_mask & short_mask, "signal"] = 0

    df["signal"] = df["signal"].astype(int)
    return df


def _build_rule_mask(df: pd.DataFrame, rules: list) -> pd.Series:
    """
    AND together all columns listed in `rules`.
    Missing or NaN values are treated as False (trade not taken).
    """
    mask = pd.Series(True, index=df.index)
    for col in rules:
        if col in df.columns:
            mask = mask & df[col].fillna(False).astype(bool)
        else:
            # Column missing means condition can never be met → no signal
            mask = pd.Series(False, index=df.index)
            break
    return mask


# ------------------------------------------------------------------ #
# Exit levels                                                          #
# ------------------------------------------------------------------ #

def build_exit_levels(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    Compute ATR-based SL and TP for each non-zero signal.

    For long  (signal ==  1): sl = close - atr*sl_mult,  tp = close + atr*tp_mult
    For short (signal == -1): sl = close + atr*sl_mult,  tp = close - atr*tp_mult

    Signals are nullified (set to 0) when:
    - ATR is NaN (insufficient history)
    - Computed SL distance (pips) is below min_stop_pips
    - Computed SL distance (pips) is above max_stop_pips
    """
    exits_cfg = config["strategy"].get("exits", {})
    sl_mult = float(exits_cfg.get("atr_sl_multiplier", 1.5))
    tp_mult = float(exits_cfg.get("atr_tp_multiplier", 2.0))

    constraints = config["risk"]["constraints"]
    min_stop_pips = float(constraints.get("min_stop_pips", 3))
    max_stop_pips = float(constraints.get("max_stop_pips", 100))

    close = df["close"]
    atr = df.get("atr", pd.Series(np.nan, index=df.index))

    sl_distance = atr * sl_mult
    tp_distance = atr * tp_mult

    sl_pips = sl_distance * 10_000.0

    # Pre-compute raw SL/TP per side (vectorised; safe for NaN ATR)
    sl_long = (close - sl_distance).round(5)
    tp_long = (close + tp_distance).round(5)
    sl_short = (close + sl_distance).round(5)
    tp_short = (close - tp_distance).round(5)

    active = df["signal"] != 0

    # Disqualification mask: ATR issues or stop outside pip limits
    bad = (
        active & (
            atr.isna()
            | (sl_pips < min_stop_pips)
            | (sl_pips > max_stop_pips)
        )
    )
    df.loc[bad, "signal"] = 0
    active = df["signal"] != 0  # recompute after disqualification

    long_mask = df["signal"] == 1
    short_mask = df["signal"] == -1

    df["sl_price"] = np.where(long_mask, sl_long,
                     np.where(short_mask, sl_short, np.nan))
    df["tp_price"] = np.where(long_mask, tp_long,
                     np.where(short_mask, tp_short, np.nan))

    # Ensure zero-signal rows have NaN exits
    df.loc[~active, "sl_price"] = np.nan
    df.loc[~active, "tp_price"] = np.nan

    return df


# ------------------------------------------------------------------ #
# Private helper                                                       #
# ------------------------------------------------------------------ #

def _ensure_pattern_columns_false(df: pd.DataFrame) -> None:
    """Create any missing pattern boolean columns as False (in-place)."""
    pattern_cols = [
        "bullish_engulfing", "bearish_engulfing", "inside_bar",
        "sweep_prev_high", "sweep_prev_low",
        "orb_breakout_long", "orb_breakout_short",
    ]
    for col in pattern_cols:
        if col not in df.columns:
            df[col] = False
