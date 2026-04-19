"""
StratForge - Risk Manager Module

Calculates position sizing and enforces risk constraints.
Supports: fixed_lot, fixed_fractional, volatility_adjusted, fractional_kelly.

POSITION SIZING ASSUMPTIONS:
- Pair assumed to be 4-decimal (e.g., EURUSD): 1 pip = 0.0001
- pip_value_per_lot = $10 per pip per standard lot (EURUSD)
- Minimum lot size: 0.01 (broker standard micro-lot)
- Size rounded to 2 decimal places

SAFETY HIERARCHY:
  constraint checks > stop-pip guards > kelly cap > max_risk_pct cap > minimum lot guard
All safety caps override AI/optimizer preferences unconditionally.
"""

from typing import Dict, Any


# Pip value for a standard lot on a 4-decimal pair priced in USD (EURUSD, GBPUSD, etc.)
_PIP_VALUE_PER_LOT = 10.0
_MIN_LOT = 0.01


def get_effective_risk_model(config: Dict, performance_state: Dict) -> str:
    """
    Determine which risk model to apply for this trade.

    Falls back to fixed_fractional if fractional_kelly is configured but
    not enabled or has insufficient trade history.
    """
    model = config["risk"].get("model", "fixed_fractional")

    if model == "fractional_kelly":
        kelly_cfg = config["risk"].get("fractional_kelly", {})
        if not kelly_cfg.get("enabled", False):
            return "fixed_fractional"

        min_trades = kelly_cfg.get("min_trades_required", 30)
        num_trades = performance_state.get("num_trades", 0)
        if num_trades < min_trades:
            return "fixed_fractional"

    return model


def check_risk_constraints(
    equity: float,
    open_positions: Any,  # int or list; backtest engine passes int
    config: Dict,
    state: Dict,
) -> bool:
    """
    Return True if a new trade is permitted under current risk constraints.

    Checks (fail-fast order):
    1. max_positions: total open positions must be below limit
    2. max_daily_loss_pct: cumulative daily loss must be below limit
    3. max_drawdown_halt_pct: account drawdown must be above halt threshold
    """
    constraints = config["risk"]["constraints"]

    # Normalise open_positions to an integer count
    n_open = open_positions if isinstance(open_positions, int) else len(open_positions)

    max_positions = constraints.get("max_positions", 1)
    if n_open >= max_positions:
        return False

    max_daily_loss_pct = constraints.get("max_daily_loss_pct", 3.0)
    daily_loss_pct = state.get("daily_loss_pct", 0.0)
    if daily_loss_pct >= max_daily_loss_pct / 100.0:
        return False

    max_drawdown_halt_pct = constraints.get("max_drawdown_halt_pct", 15.0)
    current_drawdown = state.get("current_drawdown", 0.0)  # negative float
    if current_drawdown <= -(max_drawdown_halt_pct / 100.0):
        return False

    return True


def calculate_position_size(
    signal_row: Dict,
    equity: float,
    config: Dict,
    performance_state: Dict,
) -> Dict[str, Any]:
    """
    Calculate lot size for an incoming signal.

    Returns a dict with:
        allowed     - bool: False means the trade must be skipped
        size        - float: position size in standard lots
        risk_pct    - float: effective risk as % of equity
        risk_amount - float: risk in account currency
        model_used  - str
        notes       - str: human-readable explanation
    """
    close = signal_row.get("close", 0.0)
    sl_price = signal_row.get("sl_price", None)

    # Guard: sl_price must exist and be valid
    if sl_price is None or sl_price != sl_price:  # NaN check
        return _disallowed("sl_price is missing or NaN")

    sl_distance = abs(close - sl_price)
    if sl_distance == 0.0:
        return _disallowed("sl_distance is zero (close == sl_price)")

    sl_pips = sl_distance * 10_000.0  # 4-decimal pair

    # Enforce pip constraints before sizing
    constraints = config["risk"]["constraints"]
    min_stop_pips = constraints.get("min_stop_pips", 3)
    max_stop_pips = constraints.get("max_stop_pips", 100)

    if sl_pips < min_stop_pips:
        return _disallowed(
            f"SL too tight: {sl_pips:.1f} pips < min {min_stop_pips}"
        )
    if sl_pips > max_stop_pips:
        return _disallowed(
            f"SL too wide: {sl_pips:.1f} pips > max {max_stop_pips}"
        )

    effective_model = get_effective_risk_model(config, performance_state)

    # ------------------------------------------------------------------ #
    # Model-specific sizing                                                #
    # ------------------------------------------------------------------ #

    if effective_model == "fixed_lot":
        lot = config["risk"]["fixed_lot"].get("lot", 0.10)
        size = lot
        risk_amount = sl_pips * _PIP_VALUE_PER_LOT * size
        risk_pct = (risk_amount / equity * 100.0) if equity > 0 else 0.0
        notes = f"fixed_lot={lot}"

    elif effective_model == "fixed_fractional":
        risk_pct_target = config["risk"]["fixed_fractional"].get("risk_pct", 1.0)
        risk_amount = risk_pct_target / 100.0 * equity
        size = risk_amount / (sl_pips * _PIP_VALUE_PER_LOT)
        risk_pct = risk_pct_target
        notes = f"fixed_fractional risk_pct={risk_pct_target}"

    elif effective_model == "volatility_adjusted":
        va_cfg = config["risk"].get("volatility_adjusted", {})
        risk_pct_target = va_cfg.get("risk_pct", 1.0)
        atr_size_scale = va_cfg.get("atr_size_scale", 1.0)
        risk_amount = risk_pct_target / 100.0 * equity
        size = (risk_amount / (sl_pips * _PIP_VALUE_PER_LOT)) * atr_size_scale
        risk_pct = risk_pct_target * atr_size_scale
        notes = (
            f"volatility_adjusted risk_pct={risk_pct_target} "
            f"atr_scale={atr_size_scale}"
        )

    elif effective_model == "fractional_kelly":
        kelly_cfg = config["risk"].get("fractional_kelly", {})
        kelly_fraction_cap = kelly_cfg.get("kelly_fraction_cap", 0.25)
        max_risk_pct = kelly_cfg.get("max_risk_pct", 1.5)

        win_rate = performance_state.get("win_rate", 0.0)
        payoff_ratio = performance_state.get("payoff_ratio", 0.0)

        if payoff_ratio <= 0.0:
            # Degenerate: no meaningful payoff data — fallback to fixed_fractional
            fallback_pct = config["risk"]["fixed_fractional"].get("risk_pct", 1.0)
            risk_amount = fallback_pct / 100.0 * equity
            size = risk_amount / (sl_pips * _PIP_VALUE_PER_LOT)
            risk_pct = fallback_pct
            effective_model = "fixed_fractional"
            notes = (
                f"fractional_kelly fallback (payoff_ratio=0) "
                f"-> fixed_fractional risk_pct={fallback_pct}"
            )
        else:
            raw_kelly = win_rate - (1.0 - win_rate) / payoff_ratio
            capped_kelly = max(0.0, min(raw_kelly, kelly_fraction_cap))

            if capped_kelly == 0.0:
                return _disallowed(
                    f"fractional_kelly: negative or zero Kelly "
                    f"(raw_k={raw_kelly:.4f}, win_rate={win_rate:.3f}, "
                    f"payoff={payoff_ratio:.3f})"
                )

            risk_pct_target = min(capped_kelly * 100.0, max_risk_pct)
            risk_amount = risk_pct_target / 100.0 * equity
            size = risk_amount / (sl_pips * _PIP_VALUE_PER_LOT)
            risk_pct = risk_pct_target
            notes = (
                f"fractional_kelly raw_k={raw_kelly:.4f} "
                f"capped_k={capped_kelly:.4f} risk_pct={risk_pct_target:.3f}"
            )

    else:
        return _disallowed(f"Unknown risk model: '{effective_model}'")

    # ------------------------------------------------------------------ #
    # Post-sizing guards                                                   #
    # ------------------------------------------------------------------ #

    if size < _MIN_LOT:
        return _disallowed(
            f"Computed size {size:.5f} lots below minimum {_MIN_LOT} "
            f"(equity={equity:.2f}, sl_pips={sl_pips:.1f})"
        )

    size = round(size, 2)
    risk_amount = sl_pips * _PIP_VALUE_PER_LOT * size  # recalculate after rounding

    return {
        "allowed": True,
        "size": size,
        "risk_pct": round(risk_pct, 4),
        "risk_amount": round(risk_amount, 4),
        "model_used": effective_model,
        "notes": notes,
    }


# ------------------------------------------------------------------ #
# Private helpers                                                      #
# ------------------------------------------------------------------ #

def _disallowed(reason: str) -> Dict[str, Any]:
    """Return a standard 'not allowed' sizing result."""
    return {
        "allowed": False,
        "size": 0.0,
        "risk_pct": 0.0,
        "risk_amount": 0.0,
        "model_used": "none",
        "notes": reason,
    }
