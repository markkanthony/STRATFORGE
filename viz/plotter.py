"""
plotter.py - Optional visualization layer for human review

This module generates visual artifacts for backtest runs.
It is downstream and read-only - never affects backtest results.

Supports three modes:
- off: Generate nothing
- basic: Core charts only (price, equity, drawdown, summary)
- detailed: All available charts and analysis visuals

Uses matplotlib for v1 implementation.
All human-facing time labels use display_timezone from config.
"""

import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt


def generate_visual_artifacts(run_data: Dict[str, Any], config: Dict[str, Any], out_dir: Path) -> None:
    """Main entry point for visualization generation."""
    viz_config = config.get("visualization", {})
    if not viz_config.get("enabled", False):
        return
    
    mode = viz_config.get("mode", "basic")
    if mode == "off":
        return
    
    out_dir.mkdir(parents=True, exist_ok=True)
    display_tz = config.get("time", {}).get("display_timezone", "UTC")
    
    print(f"    → Generating {mode} mode visualizations...")
    
    if mode in ["basic", "detailed"]:
        _generate_basic_charts(run_data, config, out_dir, display_tz)
    
    if mode == "detailed":
        _generate_detailed_charts(run_data, config, out_dir, display_tz)
    
    _generate_summary_html(run_data, config, out_dir, display_tz)
    print(f"    → Visualization complete")


def _generate_basic_charts(run_data: Dict[str, Any], config: Dict[str, Any],
                           out_dir: Path, display_tz: str) -> None:
    """Generate basic mode charts"""
    for window in ["train", "validation"]:
        _plot_equity_curve(run_data, window, out_dir, display_tz)
        _plot_drawdown(run_data, window, out_dir, display_tz)


def _generate_detailed_charts(run_data: Dict[str, Any], config: Dict[str, Any],
                              out_dir: Path, display_tz: str) -> None:
    """Generate detailed mode charts"""
    _plot_trade_returns_histogram(run_data, out_dir)
    _plot_r_multiples_histogram(run_data, out_dir)
    _plot_side_breakdown(run_data, out_dir)


def _plot_equity_curve(run_data: Dict[str, Any], window: str,
                       out_dir: Path, display_tz: str) -> None:
    """Plot equity curve"""
    try:
        equity_data = run_data.get(window, {}).get("equity_curve", [])
        if not equity_data or len(equity_data) < 2:
            return
        
        df = pd.DataFrame(equity_data)
        df["time"] = pd.to_datetime(df["time"])
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(df["time"], df["equity"], linewidth=2, color='blue')
        ax.fill_between(df["time"], df["equity"], alpha=0.3, color='blue')
        
        start_equity = df["equity"].iloc[0]
        ax.axhline(y=start_equity, color='gray', linestyle='--', alpha=0.5, label='Starting Capital')
        
        ax.set_title(f'{window.capitalize()} - Equity Curve', fontsize=14, fontweight='bold')
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Equity ($)', fontsize=12)
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
        
        plt.tight_layout()
        plt.savefig(out_dir / f'{window}_equity_curve.png', dpi=100, bbox_inches='tight')
        plt.close()
    except Exception as e:
        print(f"      ⚠ Skipping {window} equity curve: {e}")


def _plot_drawdown(run_data: Dict[str, Any], window: str,
                   out_dir: Path, display_tz: str) -> None:
    """Plot drawdown curve"""
    try:
        equity_data = run_data.get(window, {}).get("equity_curve", [])
        if not equity_data or len(equity_data) < 2:
            return
        
        df = pd.DataFrame(equity_data)
        df["time"] = pd.to_datetime(df["time"])
        df["peak"] = df["equity"].cummax()
        df["drawdown"] = (df["equity"] - df["peak"]) / df["peak"]
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.fill_between(df["time"], df["drawdown"], 0, alpha=0.3, color='red')
        ax.plot(df["time"], df["drawdown"], linewidth=2, color='darkred')
        
        max_dd_idx = df["drawdown"].idxmin()
        max_dd_value = df["drawdown"].iloc[max_dd_idx]
        max_dd_time = df["time"].iloc[max_dd_idx]
        ax.scatter([max_dd_time], [max_dd_value], color='darkred', s=100, zorder=5)
        
        ax.set_title(f'{window.capitalize()} - Drawdown', fontsize=14, fontweight='bold')
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Drawdown (%)', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.1%}'))
        
        plt.tight_layout()
        plt.savefig(out_dir / f'{window}_drawdown.png', dpi=100, bbox_inches='tight')
        plt.close()
    except Exception as e:
        print(f"      ⚠ Skipping {window} drawdown: {e}")


def _plot_trade_returns_histogram(run_data: Dict[str, Any], out_dir: Path) -> None:
    """Plot histogram of trade returns"""
    try:
        train_trades = run_data.get("train", {}).get("trades", [])
        val_trades = run_data.get("validation", {}).get("trades", [])
        all_trades = train_trades + val_trades
        
        if not all_trades:
            return
        
        returns = [t["pnl"] for t in all_trades]
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(returns, bins=30, alpha=0.7, color='blue', edgecolor='black')
        ax.axvline(x=0, color='red', linestyle='--', linewidth=2, label='Break-even')
        ax.axvline(x=np.mean(returns), color='green', linestyle='--', linewidth=2, label='Mean')
        
        ax.set_title('Trade Returns Distribution', fontsize=14, fontweight='bold')
        ax.set_xlabel('PnL ($)', fontsize=12)
        ax.set_ylabel('Frequency', fontsize=12)
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        plt.savefig(out_dir / 'trade_returns_histogram.png', dpi=100, bbox_inches='tight')
        plt.close()
    except Exception as e:
        print(f"      ⚠ Skipping trade returns histogram: {e}")


def _plot_r_multiples_histogram(run_data: Dict[str, Any], out_dir: Path) -> None:
    """Plot histogram of R-multiples"""
    try:
        train_trades = run_data.get("train", {}).get("trades", [])
        val_trades = run_data.get("validation", {}).get("trades", [])
        all_trades = train_trades + val_trades
        
        if not all_trades:
            return
        
        r_multiples = [t.get("r_multiple", 0) for t in all_trades if t.get("r_multiple") is not None]
        if not r_multiples:
            return
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(r_multiples, bins=30, alpha=0.7, color='purple', edgecolor='black')
        ax.axvline(x=0, color='red', linestyle='--', linewidth=2, label='Break-even')
        ax.axvline(x=np.mean(r_multiples), color='green', linestyle='--', linewidth=2, label='Mean R')
        
        ax.set_title('R-Multiple Distribution', fontsize=14, fontweight='bold')
        ax.set_xlabel('R-Multiple', fontsize=12)
        ax.set_ylabel('Frequency', fontsize=12)
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        plt.savefig(out_dir / 'r_multiples_histogram.png', dpi=100, bbox_inches='tight')
        plt.close()
    except Exception as e:
        print(f"      ⚠ Skipping R-multiples histogram: {e}")


def _plot_side_breakdown(run_data: Dict[str, Any], out_dir: Path) -> None:
    """Plot long vs short breakdown"""
    try:
        train_metrics = run_data.get("train", {}).get("metrics", {})
        val_metrics = run_data.get("validation", {}).get("metrics", {})
        
        train_side = train_metrics.get("side_breakdown", {})
        val_side = val_metrics.get("side_breakdown", {})
        
        if not train_side and not val_side:
            return
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        labels = ['Train Long', 'Train Short', 'Val Long', 'Val Short']
        win_rates = [
            train_side.get("long_win_rate", 0),
            train_side.get("short_win_rate", 0),
            val_side.get("long_win_rate", 0),
            val_side.get("short_win_rate", 0)
        ]
        ax1.bar(labels, win_rates, color=['green', 'red', 'lightgreen', 'lightcoral'])
        ax1.set_title('Win Rate by Side', fontweight='bold')
        ax1.set_ylabel('Win Rate')
        ax1.set_ylim(0, 1)
        ax1.grid(True, alpha=0.3, axis='y')
        
        pfs = [
            train_side.get("long_profit_factor", 0),
            train_side.get("short_profit_factor", 0),
            val_side.get("long_profit_factor", 0),
            val_side.get("short_profit_factor", 0)
        ]
        ax2.bar(labels, pfs, color=['green', 'red', 'lightgreen', 'lightcoral'])
        ax2.set_title('Profit Factor by Side', fontweight='bold')
        ax2.set_ylabel('Profit Factor')
        ax2.axhline(y=1.0, color='black', linestyle='--', alpha=0.5)
        ax2.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        plt.savefig(out_dir / 'side_breakdown.png', dpi=100, bbox_inches='tight')
        plt.close()
    except Exception as e:
        print(f"      ⚠ Skipping side breakdown: {e}")


def _generate_summary_html(run_data: Dict[str, Any], config: Dict[str, Any],
                           out_dir: Path, display_tz: str) -> None:
    """Generate HTML summary report"""
    try:
        train_m = run_data.get("train", {}).get("metrics", {})
        val_m = run_data.get("validation", {}).get("metrics", {})
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>StratForge Run {run_data['run']} Summary</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: auto; background: white; padding: 20px; }}
        h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; border-bottom: 2px solid #ddd; padding-bottom: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>StratForge Backtest Run {run_data['run']}</h1>
        
        <h2>Run Metadata</h2>
        <p><strong>Symbol:</strong> {run_data['symbol']}</p>
        <p><strong>Timeframe:</strong> {run_data['timeframe']}</p>
        <p><strong>Timestamp:</strong> {run_data['timestamp']}</p>
        <p><strong>Display Timezone:</strong> {display_tz}</p>
        
        <h2>Performance Comparison</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Train</th>
                <th>Validation</th>
            </tr>
            <tr>
                <td>Sharpe Ratio</td>
                <td>{train_m.get('performance', {}).get('sharpe', 'N/A')}</td>
                <td>{val_m.get('performance', {}).get('sharpe', 'N/A')}</td>
            </tr>
            <tr>
                <td>Total Return</td>
                <td>{train_m.get('performance', {}).get('total_return', 'N/A')}</td>
                <td>{val_m.get('performance', {}).get('total_return', 'N/A')}</td>
            </tr>
            <tr>
                <td>Max Drawdown</td>
                <td>{train_m.get('risk', {}).get('max_drawdown', 'N/A')}</td>
                <td>{val_m.get('risk', {}).get('max_drawdown', 'N/A')}</td>
            </tr>
            <tr>
                <td>Num Trades</td>
                <td>{train_m.get('trades', {}).get('num_trades', 'N/A')}</td>
                <td>{val_m.get('trades', {}).get('num_trades', 'N/A')}</td>
            </tr>
        </table>
        
        <h2>Charts</h2>
        <p>See generated PNG files in this directory for visual analysis.</p>
    </div>
</body>
</html>"""
        
        html_path = out_dir / "summary.html"
        html_path.write_text(html, encoding="utf-8")
    except Exception as e:
        print(f"      ⚠ Skipping summary HTML: {e}")
