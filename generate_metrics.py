#!/usr/bin/env python3
"""Temporary script to generate complete metrics.py"""

metrics_content = """\"\"\"
metrics.py

Compute rich output metrics for a backtest window.

ANNUALIZATION ASSUMPTIONS:
- Assumes 252 trading days per year
- For forex H1 bars: ~6000 bars per year (252 days * ~24 hours)
- Sharpe uses sqrt(bars_per_year) for annualization
- Annualized return uses simple linear scaling based on period length

ZERO-TRADE SAFETY:
- All metrics return safe defaults (0.0, None, or empty structures) when no trades
- Division by zero is guarded
- Empty arrays handled gracefully
\"\"\"

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional


def compute_metrics(backtest_result, config, run_number, window_label):
    trades = backtest_result.get("trades", [])
    equity_curve = backtest_result.get("equity_curve", [])
    trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
    equity_df = pd.DataFrame(equity_curve) if equity_curve else pd.DataFrame()
    
    return {
        "run_number": run_number, "window_label": window_label,
        "performance": compute_performance_metrics(trades_df, equity_df, config),
        "risk": compute_risk_metrics(equity_df, trades_df, config),
        "trades": compute_trade_metrics(trades_df, equity_df, config),
        "streaks": compute_streak_metrics(trades_df),
        "side_breakdown": compute_side_breakdown_metrics(trades_df),
        "diagnostics": compute_diagnostics_metrics(trades_df, equity_df),
        "risk_sizing": compute_risk_sizing_metrics(trades_df, backtest_result, config),
        "time_breakdown": compute_time_breakdown_metrics(trades_df)
    }


def compute_performance_metrics(trades_df, equity_df, config):
    if equity_df.empty:
        return {"total_return": 0.0, "annualized_return": 0.0, "sharpe": 0.0, "sortino": 0.0, "calmar": 0.0}
    initial_capital, final_equity = config["backtest"]["capital"], equity_df["equity"].iloc[-1]
    total_return = (final_equity - initial_capital) / initial_capital
    years = len(equity_df) / 6000 if len(equity_df) > 0 else 1
    annualized_return = total_return / years if years > 0 else 0.0
    
    if len(equity_df) > 1:
        equity_df = equity_df.copy()
        equity_df["returns"] = equity_df["equity"].pct_change()
        returns = equity_df["returns"].dropna()
        sharpe = returns.mean() / returns.std() * np.sqrt(6000) if len(returns) > 0 and returns.std() > 0 else 0.0
        downside = returns[returns < 0]
        sortino = returns.mean() / downside.std() * np.sqrt(6000) if len(downside) > 0 and downside.std() > 0 else 0.0
    else:
        sharpe, sortino = 0.0, 0.0
    
    max_dd = compute_max_drawdown(equity_df)
    calmar = annualized_return / abs(max_dd) if max_dd < 0 else 0.0
    return {"total_return": round(total_return, 4), "annualized_return": round(annualized_return, 4), "sharpe": round(sharpe, 4), "sortino": round(sortino, 4), "calmar": round(calmar, 4)}


def compute_risk_metrics(equity_df, trades_df, config):
    if equity_df.empty:
        return {"max_drawdown": 0.0, "avg_drawdown": 0.0, "max_drawdown_duration_bars": 0, "time_to_recover_bars": 0, "ulcer_index": 0.0, "recovery_factor": 0.0, "return_on_max_drawdown": 0.0}
    max_dd, avg_dd = compute_max_drawdown(equity_df), compute_avg_drawdown(equity_df)
    dd_duration, recovery_bars, ulcer = compute_max_drawdown_duration(equity_df), compute_time_to_recover(equity_df), compute_ulcer_index(equity_df)
    initial_capital, final_equity = config["backtest"]["capital"], equity_df["equity"].iloc[-1]
    total_return = (final_equity - initial_capital) / initial_capital
    recovery_factor = total_return / abs(max_dd) if max_dd < 0 else 0.0
    return {"max_drawdown": round(max_dd, 4), "avg_drawdown": round(avg_dd, 4), "max_drawdown_duration_bars": dd_duration, "time_to_recover_bars": recovery_bars, "ulcer_index": round(ulcer, 4), "recovery_factor": round(recovery_factor, 4), "return_on_max_drawdown": round(recovery_factor, 4)}


def compute_trade_metrics(trades_df, equity_df, config):
    if trades_df.empty:
        return {"num_trades": 0, "win_rate": 0.0, "loss_rate": 0.0, "profit_factor": 0.0, "expectancy": 0.0, "avg_win": 0.0, "avg_loss": 0.0, "payoff_ratio": 0.0, "avg_r_multiple": 0.0, "best_trade": 0.0, "worst_trade": 0.0, "median_trade_return": 0.0, "std_trade_return": 0.0, "avg_trade_bars": 0.0, "trades_per_month": 0.0}
    num_trades, wins, losses = len(trades_df), trades_df[trades_df["pnl"] > 0], trades_df[trades_df["pnl"] < 0]
    win_rate, loss_rate = len(wins) / num_trades if num_trades > 0 else 0.0, len(losses) / num_trades if num_trades > 0 else 0.0
    total_wins, total_losses = wins["pnl"].sum() if not wins.empty else 0.0, abs(losses["pnl"].sum()) if not losses.empty else 0.0
    profit_factor = total_wins / total_losses if total_losses > 0 else 0.0
    expectancy, avg_win, avg_loss = trades_df["pnl"].mean() if not trades_df.empty else 0.0, wins["pnl"].mean() if not wins.empty else 0.0, losses["pnl"].mean() if not losses.empty else 0.0
    payoff_ratio = abs(avg_win / avg_loss) if avg_loss < 0 else 0.0
    avg_r = trades_df["r_multiple"].mean() if "r_multiple" in trades_df.columns else 0.0
    best_trade, worst_trade = trades_df["pnl"].max() if not trades_df.empty else 0.0, trades_df["pnl"].min() if not trades_df.empty else 0.0
    median_return, std_return = trades_df["pnl_pct"].median() if "pnl_pct" in trades_df.columns else 0.0, trades_df["pnl_pct"].std() if "pnl_pct" in trades_df.columns else 0.0
    avg_bars = trades_df["bars_held"].mean() if "bars_held" in trades_df.columns else 0.0
    if not trades_df.empty and "entry_time" in trades_df.columns:
        trades_df = trades_df.copy()
        trades_df["entry_time"] = pd.to_datetime(trades_df["entry_time"])
        months = (trades_df["entry_time"].max() - trades_df["entry_time"].min()).days / 30 if (trades_df["entry_time"].max() - trades_df["entry_time"].min()).days > 0 else 1
        trades_per_month = num_trades / months
    else:
        trades_per_month = 0.0
    return {"num_trades": num_trades, "win_rate": round(win_rate, 4), "loss_rate": round(loss_rate, 4), "profit_factor": round(profit_factor, 4), "expectancy": round(expectancy, 2), "avg_win": round(avg_win, 2), "avg_loss": round(avg_loss, 2), "payoff_ratio": round(payoff_ratio, 4), "avg_r_multiple": round(avg_r, 4), "best_trade": round(best_trade, 2), "worst_trade": round(worst_trade, 2), "median_trade_return": round(median_return, 4), "std_trade_return": round(std_return, 4), "avg_trade_bars": round(avg_bars, 2), "trades_per_month": round(trades_per_month, 2)}


def compute_streak_metrics(trades_df):
    if trades_df.empty:
        return {"max_consecutive_wins": 0, "max_consecutive_losses": 0, "avg_consecutive_wins": 0.0, "avg_consecutive_losses": 0.0, "current_consecutive_wins": 0, "current_consecutive_losses": 0}
    trades_df = trades_df.copy()
    trades_df["is_win"] = trades_df["pnl"] > 0
    win_streaks, loss_streaks, current_streak, current_type = [], [], 0, None
    for is_win in trades_df["is_win"]:
        if is_win:
            if current_type == "win":
                current_streak += 1
            else:
                if current_type == "loss" and current_streak > 0:
                    loss_streaks.append(current_streak)
                current_streak, current_type = 1, "win"
        else:
            if current_type == "loss":
                current_streak += 1
            else:
                if current_type == "win" and current_streak > 0:
                    win_streaks.append(current_streak)
                current_streak, current_type = 1, "loss"
    if current_type == "win" and current_streak > 0:
        win_streaks.append(current_streak)
    elif current_type == "loss" and current_streak > 0:
        loss_streaks.append(current_streak)
    current_wins, current_losses = win_streaks[-1] if win_streaks and current_type == "win" else 0, loss_streaks[-1] if loss_streaks and current_type == "loss" else 0
    return {"max_consecutive_wins": max(win_streaks) if win_streaks else 0, "max_consecutive_losses": max(loss_streaks) if loss_streaks else 0, "avg_consecutive_wins": round(sum(win_streaks) / len(win_streaks), 2) if win_streaks else 0.0, "avg_consecutive_losses": round(sum(loss_streaks) / len(loss_streaks), 2) if loss_streaks else 0.0, "current_consecutive_wins": current_wins, "current_consecutive_losses": current_losses}


def compute_side_breakdown_metrics(trades_df):
    if trades_df.empty or "side" not in trades_df.columns:
        return {"long_trades": 0, "short_trades": 0, "long_win_rate": 0.0, "short_win_rate": 0.0, "long_profit_factor": 0.0, "short_profit_factor": 0.0}
    longs, shorts = trades_df[trades_df["side"] == "long"], trades_df[trades_df["side"] == "short"]
    long_wins, long_losses = longs[longs["pnl"] > 0], longs[longs["pnl"] < 0]
    long_win_rate = len(long_wins) / len(longs) if len(longs) > 0 else 0.0
    long_pf = long_wins["pnl"].sum() / abs(long_losses["pnl"].sum()) if not long_losses.empty and long_losses["pnl"].sum() < 0 else 0.0
    short_wins, short_losses = shorts[shorts["pnl"] > 0], shorts[shorts["pnl"] < 0]
    short_win_rate = len(short_wins) / len(shorts) if len(shorts) > 0 else 0.0
    short_pf = short_wins["pnl"].sum() / abs(short_losses["pnl"].sum()) if not short_losses.empty and short_losses["pnl"].sum() < 0 else 0.0
    return {"long_trades": len(longs), "short_trades": len(shorts), "long_win_rate": round(long_win_rate, 4), "short_win_rate": round(short_win_rate, 4), "long_profit_factor": round(long_pf, 4), "short_profit_factor": round(short_pf, 4)}


def compute_diagnostics_metrics(trades_df, equity_df):
    if trades_df.empty:
        return {"max_consecutive_losses": 0, "long_win_rate": 0.0, "short_win_rate": 0.0, "avg_trade_bars": 0.0}
    side_breakdown = compute_side_breakdown_metrics(trades_df)
    streaks = compute_streak_metrics(trades_df)
    avg_bars = trades_df["bars_held"].mean() if "bars_held" in trades_df.columns else 0.0
    return {"max_consecutive_losses": streaks["max_consecutive_losses"], "long_win_rate": side_breakdown["long_win_rate"], "short_win_rate": side_breakdown["short_win_rate"], "avg_trade_bars": round(avg_bars, 2)}


def compute_risk_sizing_metrics(trades_df, backtest_result, config):
    if trades_df.empty:
        return {"avg_position_size": 0.0, "max_position_size": 0.0, "min_position_size": 0.0, "avg_risk_pct_per_trade": 0.0, "max_risk_pct_per_trade": 0.0, "sizing_model_used": "unknown", "kelly_estimate": None, "kelly_fraction_applied": None, "fallback_to_fixed_fractional_count": 0, "risk_halt_triggered": False}
    avg_size = trades