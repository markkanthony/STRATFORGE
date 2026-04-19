"""Indicator and pattern catalog for the visual strategy builder."""

from fastapi import APIRouter

from api.schemas import IndicatorMeta, PatternMeta


router = APIRouter(prefix="/api/library", tags=["library"])


INDICATORS = [
    {
        "name": "ema",
        "display_name": "EMA",
        "category": "Trend",
        "description": "Exponential moving average of close price.",
        "params": [{"name": "period", "type": "int", "default": 10, "min": 2, "max": 500, "label": "Period"}],
    },
    {
        "name": "sma",
        "display_name": "EMA Slow",
        "category": "Trend",
        "description": "Secondary EMA used as the slow comparison line in crossover and state rules.",
        "params": [{"name": "period", "type": "int", "default": 20, "min": 2, "max": 500, "label": "Period"}],
    },
    {
        "name": "ema_trend",
        "display_name": "EMA Trend",
        "category": "Trend",
        "description": "Third EMA used as a higher-order trend anchor for 3-EMA stack rules.",
        "params": [{"name": "period", "type": "int", "default": 200, "min": 2, "max": 500, "label": "Period"}],
    },
    {
        "name": "rsi",
        "display_name": "RSI",
        "category": "Momentum",
        "description": "Relative strength index with Wilder smoothing.",
        "params": [{"name": "period", "type": "int", "default": 14, "min": 2, "max": 100, "label": "Period"}],
    },
    {
        "name": "atr",
        "display_name": "ATR",
        "category": "Volatility",
        "description": "Average true range used for stop and target sizing.",
        "params": [{"name": "period", "type": "int", "default": 14, "min": 2, "max": 100, "label": "Period"}],
    },
    {
        "name": "macd",
        "display_name": "MACD",
        "category": "Momentum",
        "description": "MACD line and signal relationship for momentum shifts.",
        "params": [
            {"name": "fast", "type": "int", "default": 12, "min": 2, "max": 100, "label": "Fast"},
            {"name": "slow", "type": "int", "default": 26, "min": 2, "max": 200, "label": "Slow"},
            {"name": "signal", "type": "int", "default": 9, "min": 2, "max": 50, "label": "Signal"},
        ],
    },
    {
        "name": "bollinger",
        "display_name": "Bollinger Bands",
        "category": "Volatility",
        "description": "Mid-band and band width for compression and expansion.",
        "params": [
            {"name": "period", "type": "int", "default": 20, "min": 2, "max": 200, "label": "Period"},
            {"name": "std", "type": "float", "default": 2.0, "min": 0.5, "max": 5.0, "label": "Std Dev"},
        ],
    },
    {
        "name": "stochastic",
        "display_name": "Stochastic",
        "category": "Momentum",
        "description": "Fast and slow stochastic oscillator values.",
        "params": [
            {"name": "period", "type": "int", "default": 14, "min": 2, "max": 100, "label": "Period"},
            {"name": "smooth", "type": "int", "default": 3, "min": 1, "max": 20, "label": "Smooth"},
        ],
    },
]

PATTERNS = [
    {
        "name": "bullish_engulfing",
        "display_name": "Bullish Engulfing",
        "category": "Candlestick",
        "description": "Current bullish candle engulfs the previous bearish body.",
        "params": [],
    },
    {
        "name": "bearish_engulfing",
        "display_name": "Bearish Engulfing",
        "category": "Candlestick",
        "description": "Current bearish candle engulfs the previous bullish body.",
        "params": [],
    },
    {
        "name": "sweep_prev_low",
        "display_name": "Sweep Previous Low",
        "category": "Liquidity",
        "description": "Price sweeps the prior low then closes back above it.",
        "params": [],
    },
    {
        "name": "sweep_prev_high",
        "display_name": "Sweep Previous High",
        "category": "Liquidity",
        "description": "Price sweeps the prior high then closes back below it.",
        "params": [],
    },
    {
        "name": "inside_bar",
        "display_name": "Inside Bar",
        "category": "Structure",
        "description": "Current bar stays inside the previous bar range.",
        "params": [],
    },
    {
        "name": "orb_breakout_long",
        "display_name": "ORB Breakout Long",
        "category": "Opening Range",
        "description": "Breakout above the opening range high.",
        "params": [{"name": "bars", "type": "int", "default": 3, "min": 1, "max": 12, "label": "Bars"}],
    },
    {
        "name": "orb_breakout_short",
        "display_name": "ORB Breakout Short",
        "category": "Opening Range",
        "description": "Breakout below the opening range low.",
        "params": [{"name": "bars", "type": "int", "default": 3, "min": 1, "max": 12, "label": "Bars"}],
    },
]


@router.get("/indicators", response_model=list[IndicatorMeta])
async def get_indicators() -> list[dict]:
    return INDICATORS


@router.get("/patterns", response_model=list[PatternMeta])
async def get_patterns() -> list[dict]:
    return PATTERNS
