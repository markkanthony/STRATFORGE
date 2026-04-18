"""
StratForge - Strategy Module

Provides a pluggable strategy architecture:

    BaseStrategy          – abstract interface; any strategy must implement generate_signals()
    IndicatorSpec         – named indicator descriptor (name + callable + plot hints)
    PatternSpec           – named pattern descriptor (name + callable)
    ComposableStrategy    – build a strategy programmatically with lambdas
    ConfigStrategy        – wraps the YAML-config-driven pipeline (AI loop path)

BACKWARD COMPATIBILITY:
    The module-level generate_signals(df, config) function is preserved so that
    existing callers (validator.py lookahead test, run.py default path) keep
    working without change.

PIPELINE (ConfigStrategy / internal helpers):
    generate_signals
      -> build_indicator_features   (EMA, RSI, ATR)
      -> build_pattern_features     (engulfing, inside bar, sweeps, ORB)
      -> build_context_features     (trend, prev-day levels, session)
      -> evaluate_rules             (config-driven signal column)
      -> build_exit_levels          (ATR-based SL/TP)

NO-LOOKAHEAD GUARANTEE:
    All pattern features use shift(1) for prior-bar data.
    Trend direction shifts EMA by 1 (conservative).
    ATR uses close.shift(1) for True Range.
    ORB is forward-filled within each day, never backward.
    Previous-day H/L is shifted 1 day before merging.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
import pandas as pd
import numpy as np


# ================================================================== #
# Abstract base                                                        #
# ================================================================== #

class BaseStrategy(ABC):
    """
    All strategies must inherit this class and implement generate_signals().

    The output DataFrame must contain:
        signal    int   {-1, 0, 1}
        sl_price  float | NaN  (NaN when signal == 0)
        tp_price  float | NaN  (NaN when signal == 0)
    """

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of df with signal, sl_price, tp_price columns added."""
        ...

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


# ================================================================== #
# Descriptor dataclasses                                               #
# ================================================================== #

@dataclass
class IndicatorSpec:
    """
    Descriptor for a named indicator.

    Attributes:
        name    Column name written to the DataFrame.
        fn      Callable(df) -> pd.Series. Receives the full working DataFrame.
        panel   Hint for plotter: 'price' (overlay) or a subplot name.
        overlay True if drawn on the price panel; False for separate subplot.
    """
    name: str
    fn: Callable[[pd.DataFrame], pd.Series]
    panel: str = "price"
    overlay: bool = True


@dataclass
class PatternSpec:
    """
    Descriptor for a named boolean pattern.

    Attributes:
        name  Column name written to the DataFrame (boolean Series).
        fn    Callable(df) -> pd.Series[bool].
    """
    name: str
    fn: Callable[[pd.DataFrame], pd.Series]


# ================================================================== #
# Composable (programmatic) strategy                                   #
# ================================================================== #

class ComposableStrategy(BaseStrategy):
    """
    Build a strategy by registering indicators and patterns as callables,
    then declaring entry rules and exit parameters.

    All methods return `self` for fluent chaining.

    Usage
    -----
        from strategy import ComposableStrategy
        from indicators import ema, atr
        from patterns import bullish_engulfing, sweep_prev_low

        s = (ComposableStrategy("EMA_Sweep")
             .add_indicator("ema_fast", lambda df: ema(df, 10))
             .add_indicator("ema_slow", lambda df: ema(df, 50))
             .add_indicator("atr",      lambda df: atr(df, 14))
             .add_pattern("bullish_engulfing", bullish_engulfing)
             .add_pattern("sweep_prev_low",    sweep_prev_low)
             .set_entry(
                 long=["trend_up", "sweep_prev_low", "bullish_engulfing"],
                 short=[],
             )
             .set_exit(sl_mult=1.5, tp_mult=2.0))

        signals_df = s.generate_signals(ohlcv_df)
    """

    def __init__(self, name: str = "ComposableStrategy"):
        self._name = name
        self._indicators: List[IndicatorSpec] = []
        self._patterns: List[PatternSpec] = []
        self._long_rules: List[str] = []
        self._short_rules: List[str] = []
        self._sl_mult: float = 1.5
        self._tp_mult: float = 2.0
        self._min_stop_pips: float = 3.0
        self._max_stop_pips: float = 100.0

    @property
    def name(self) -> str:
        return self._name

    # ---- Fluent builder ------------------------------------------- #

    def add_indicator(
        self,
        name: str,
        fn: Callable[[pd.DataFrame], pd.Series],
        panel: str = "price",
        overlay: bool = True,
    ) -> "ComposableStrategy":
        """Register a named indicator function."""
        self._indicators.append(IndicatorSpec(name, fn, panel, overlay))
        return self

    def add_pattern(
        self,
        name: str,
        fn: Callable[[pd.DataFrame], pd.Series],
    ) -> "ComposableStrategy":
        """Register a named boolean pattern function."""
        self._patterns.append(PatternSpec(name, fn))
        return self

    def set_entry(
        self,
        long: List[str],
        short: List[str],
    ) -> "ComposableStrategy":
        """
        Declare entry rules as lists of column names.
        All columns in `long` must be True for a long signal.
        All columns in `short` must be True for a short signal.
        """
        self._long_rules = list(long)
        self._short_rules = list(short)
        return self

    def set_exit(
        self,
        sl_mult: float = 1.5,
        tp_mult: float = 2.0,
        min_stop_pips: float = 3.0,
        max_stop_pips: float = 100.0,
    ) -> "ComposableStrategy":
        """ATR-based exit parameters. Requires an 'atr' indicator to be registered."""
        self._sl_mult = sl_mult
        self._tp_mult = tp_mult
        self._min_stop_pips = min_stop_pips
        self._max_stop_pips = max_stop_pips
        return self

    # ---- Signal generation ---------------------------------------- #

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Apply indicator functions in registration order
        for spec in self._indicators:
            result = spec.fn(df)
            df[spec.name] = result

        # Apply pattern functions
        for spec in self._patterns:
            result = spec.fn(df)
            df[spec.name] = pd.Series(result, index=df.index).fillna(False).astype(bool)

        # Derive trend_up / trend_down from ema_fast / ema_slow if available
        if "ema_fast" in df.columns and "ema_slow" in df.columns:
            prev_fast = df["ema_fast"].shift(1)
            prev_slow = df["ema_slow"].shift(1)
            df["trend_up"]   = (prev_fast > prev_slow).fillna(False)
            df["trend_down"] = (prev_fast < prev_slow).fillna(False)
        else:
            df.setdefault("trend_up",   False)
            df.setdefault("trend_down", False)

        # Session column — always required by backtest_engine
        if "session" not in df.columns:
            df["session"] = _label_sessions(df)

        # Evaluate entry rules
        df = _apply_rules(df, self._long_rules, self._short_rules)

        # ATR-based exits
        df = _apply_exits(
            df, self._sl_mult, self._tp_mult,
            self._min_stop_pips, self._max_stop_pips,
        )

        # Final guarantees
        df["signal"] = df["signal"].fillna(0).astype(int)
        for col in ("sl_price", "tp_price"):
            if col not in df.columns:
                df[col] = np.nan

        return df


# ================================================================== #
# Config-driven strategy (AI loop path)                               #
# ================================================================== #

class ConfigStrategy(BaseStrategy):
    """
    YAML-config-driven strategy.

    Reads all strategy settings from the config dict — indicators, patterns,
    entry rules, exit multipliers. This is the path used by run.py by default
    and by ai_loop.py when proposing config changes.
    """

    def __init__(self, config: dict):
        self.config = config

    @property
    def name(self) -> str:
        mode = self.config.get("strategy", {}).get("mode", "hybrid")
        return f"ConfigStrategy({mode})"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        return _generate_from_config(df, self.config)


# ================================================================== #
# Module-level backward-compat shim                                   #
# ================================================================== #

def generate_signals(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    Backward-compatible entry point.
    Delegates to ConfigStrategy — existing callers are unaffected.
    """
    return ConfigStrategy(config).generate_signals(df)


# ================================================================== #
# ConfigStrategy internals (unchanged logic from original strategy.py) #
# ================================================================== #

def _generate_from_config(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    mode = config["strategy"].get("mode", "hybrid")
    df = df.copy()

    if mode in ("indicator", "hybrid"):
        df = build_indicator_features(df, config)

    if mode in ("pattern", "hybrid"):
        df = build_pattern_features(df, config)

    df = build_context_features(df, config)

    if mode == "pattern":
        for col in ("ema_fast", "ema_slow", "rsi", "atr", "tr"):
            if col not in df.columns:
                df[col] = np.nan
        for col in ("trend_up", "trend_down"):
            if col not in df.columns:
                df[col] = False

    if mode == "indicator":
        _ensure_pattern_columns_false(df)

    df = evaluate_rules(df, config)
    df = build_exit_levels(df, config)

    df["signal"] = df["signal"].fillna(0).astype(int)
    for col in ("sl_price", "tp_price"):
        if col not in df.columns:
            df[col] = np.nan

    return df


def build_indicator_features(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """Add EMA fast/slow, RSI, and ATR columns."""
    ind_cfg = config["strategy"].get("indicators", {})
    fast_period = int(ind_cfg.get("fast_ema", 10))
    slow_period = int(ind_cfg.get("slow_ema", 50))
    rsi_period  = int(ind_cfg.get("rsi_period", 14))
    atr_period  = int(ind_cfg.get("atr_period", 14))

    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    df["ema_fast"] = close.ewm(span=fast_period, adjust=False).mean()
    df["ema_slow"] = close.ewm(span=slow_period, adjust=False).mean()

    delta    = close.diff(1)
    gain     = delta.clip(lower=0.0)
    loss     = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(com=rsi_period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=rsi_period - 1, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0.0, np.nan)
    df["rsi"] = (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)

    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low  - prev_close).abs()
    df["tr"]  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["atr"] = df["tr"].ewm(com=atr_period - 1, adjust=False).mean()

    return df


def build_pattern_features(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """Add boolean pattern columns from config."""
    pat_cfg    = config["strategy"].get("patterns", {})
    prev_open  = df["open"].shift(1)
    prev_close = df["close"].shift(1)
    prev_high  = df["high"].shift(1)
    prev_low   = df["low"].shift(1)

    if pat_cfg.get("bullish_engulfing", False):
        df["bullish_engulfing"] = (
            (prev_open > prev_close)
            & (df["close"] > df["open"])
            & (df["open"] <= prev_close)
            & (df["close"] >= prev_open)
        )
    else:
        df["bullish_engulfing"] = False

    if pat_cfg.get("bearish_engulfing", False):
        df["bearish_engulfing"] = (
            (prev_open < prev_close)
            & (df["close"] < df["open"])
            & (df["open"] >= prev_close)
            & (df["close"] <= prev_open)
        )
    else:
        df["bearish_engulfing"] = False

    if pat_cfg.get("inside_bar_breakout", False):
        df["inside_bar"] = (df["high"] < prev_high) & (df["low"] > prev_low)
    else:
        df["inside_bar"] = False

    if pat_cfg.get("sweep_prev_high", False):
        df["sweep_prev_high"] = (df["high"] > prev_high) & (df["close"] < prev_high)
    else:
        df["sweep_prev_high"] = False

    if pat_cfg.get("sweep_prev_low", False):
        df["sweep_prev_low"] = (df["low"] < prev_low) & (df["close"] > prev_low)
    else:
        df["sweep_prev_low"] = False

    orb_cfg = pat_cfg.get("orb", {})
    if orb_cfg.get("enabled", False):
        df = _build_orb_features(df, int(orb_cfg.get("bars", 3)))
    else:
        df["orb_high"] = np.nan
        df["orb_low"]  = np.nan
        df["orb_breakout_long"]  = False
        df["orb_breakout_short"] = False

    return df


def build_context_features(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """Add trend_up/down, prev-day levels, and session label."""
    ctx_cfg = config["strategy"].get("context", {})

    trend_filter = ctx_cfg.get("trend_filter", "ema")
    if trend_filter == "ema" and "ema_fast" in df.columns and "ema_slow" in df.columns:
        prev_fast = df["ema_fast"].shift(1)
        prev_slow = df["ema_slow"].shift(1)
        df["trend_up"]   = (prev_fast > prev_slow).fillna(False)
        df["trend_down"] = (prev_fast < prev_slow).fillna(False)
    else:
        df["trend_up"]   = False
        df["trend_down"] = False

    if ctx_cfg.get("use_prev_day_levels", False):
        df = _build_prev_day_levels(df)
    else:
        df["prev_day_high"] = np.nan
        df["prev_day_low"]  = np.nan

    if ctx_cfg.get("use_session_filter", False):
        df["session"] = _label_sessions(df)
    else:
        df["session"] = "all"

    return df


def evaluate_rules(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """Produce signal column from config entry rules."""
    entry_cfg   = config["strategy"].get("entry", {})
    long_rules  = entry_cfg.get("long_require_all", [])
    short_rules = entry_cfg.get("short_require_all", [])
    return _apply_rules(df, long_rules, short_rules)


def build_exit_levels(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """Compute ATR-based SL/TP from config exits settings."""
    exits_cfg = config["strategy"].get("exits", {})
    sl_mult   = float(exits_cfg.get("atr_sl_multiplier", 1.5))
    tp_mult   = float(exits_cfg.get("atr_tp_multiplier", 2.0))

    constraints    = config["risk"]["constraints"]
    min_stop_pips  = float(constraints.get("min_stop_pips", 3))
    max_stop_pips  = float(constraints.get("max_stop_pips", 100))

    return _apply_exits(df, sl_mult, tp_mult, min_stop_pips, max_stop_pips)


# ================================================================== #
# Shared helpers (used by both strategy paths)                         #
# ================================================================== #

def _apply_rules(
    df: pd.DataFrame,
    long_rules: List[str],
    short_rules: List[str],
) -> pd.DataFrame:
    """AND-combine rule lists into signal column."""
    long_mask  = _build_rule_mask(df, long_rules)
    short_mask = _build_rule_mask(df, short_rules)

    df["signal"] = 0
    df.loc[long_mask,  "signal"] = 1
    df.loc[short_mask, "signal"] = -1
    df.loc[long_mask & short_mask, "signal"] = 0  # conflict → no trade
    df["signal"] = df["signal"].astype(int)
    return df


def _apply_exits(
    df: pd.DataFrame,
    sl_mult: float,
    tp_mult: float,
    min_stop_pips: float,
    max_stop_pips: float,
) -> pd.DataFrame:
    """Compute ATR-based SL/TP; disqualify signals with bad stop distances."""
    close = df["close"]
    atr   = df.get("atr", pd.Series(np.nan, index=df.index))

    sl_distance = atr * sl_mult
    tp_distance = atr * tp_mult
    sl_pips     = sl_distance * 10_000.0

    sl_long  = (close - sl_distance).round(5)
    tp_long  = (close + tp_distance).round(5)
    sl_short = (close + sl_distance).round(5)
    tp_short = (close - tp_distance).round(5)

    active = df["signal"] != 0
    bad = active & (
        atr.isna()
        | (sl_pips < min_stop_pips)
        | (sl_pips > max_stop_pips)
    )
    df.loc[bad, "signal"] = 0
    active = df["signal"] != 0

    long_mask  = df["signal"] == 1
    short_mask = df["signal"] == -1

    df["sl_price"] = np.where(long_mask,  sl_long,
                     np.where(short_mask, sl_short, np.nan))
    df["tp_price"] = np.where(long_mask,  tp_long,
                     np.where(short_mask, tp_short, np.nan))

    df.loc[~active, "sl_price"] = np.nan
    df.loc[~active, "tp_price"] = np.nan
    return df


def _build_rule_mask(df: pd.DataFrame, rules: List[str]) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for col in rules:
        if col in df.columns:
            mask = mask & df[col].fillna(False).astype(bool)
        else:
            return pd.Series(False, index=df.index)
    return mask


def _label_sessions(df: pd.DataFrame) -> pd.Series:
    """UTC-hour session labels: overlap > newyork > london > asia > off."""
    hour = df["time"].dt.hour
    session = pd.Series("off", index=df.index)
    session = session.where(~((hour >= 0)  & (hour < 8)),  other="asia")
    session = session.where(~((hour >= 7)  & (hour < 16)), other="london")
    session = session.where(~((hour >= 12) & (hour < 21)), other="newyork")
    session = session.where(~((hour >= 12) & (hour < 16)), other="overlap")
    return session


def _build_prev_day_levels(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["_date"] = df["time"].dt.date
    daily = (
        df.groupby("_date")
        .agg(day_high=("high", "max"), day_low=("low", "min"))
        .reset_index()
        .sort_values("_date")
    )
    daily["prev_day_high"] = daily["day_high"].shift(1)
    daily["prev_day_low"]  = daily["day_low"].shift(1)
    daily = daily[["_date", "prev_day_high", "prev_day_low"]]
    df = df.merge(daily, on="_date", how="left")
    df.drop(columns=["_date"], inplace=True)
    return df


def _build_orb_features(df: pd.DataFrame, orb_bars: int) -> pd.DataFrame:
    df = df.copy()
    df["_date"]       = df["time"].dt.date
    df["_bar_of_day"] = df.groupby("_date").cumcount()

    is_orb   = df["_bar_of_day"] < orb_bars
    orb_highs = df.loc[is_orb].groupby("_date")["high"].max()
    orb_lows  = df.loc[is_orb].groupby("_date")["low"].min()

    df["orb_high"] = df["_date"].map(orb_highs)
    df["orb_low"]  = df["_date"].map(orb_lows)

    after_orb = df["_bar_of_day"] >= orb_bars
    df["orb_breakout_long"]  = after_orb & df["orb_high"].notna() & (df["close"] > df["orb_high"])
    df["orb_breakout_short"] = after_orb & df["orb_low"].notna()  & (df["close"] < df["orb_low"])

    df.loc[is_orb, ["orb_high", "orb_low"]] = np.nan
    df.loc[is_orb, ["orb_breakout_long", "orb_breakout_short"]] = False

    df.drop(columns=["_date", "_bar_of_day"], inplace=True)
    return df


def _ensure_pattern_columns_false(df: pd.DataFrame) -> None:
    for col in (
        "bullish_engulfing", "bearish_engulfing", "inside_bar",
        "sweep_prev_high", "sweep_prev_low",
        "orb_breakout_long", "orb_breakout_short",
    ):
        if col not in df.columns:
            df[col] = False
