"""
StratForge - Backtest Engine Module

Deterministic bar-by-bar backtest engine.

FILL ORDER ASSUMPTIONS:
1. Signals are generated on bar i
2. Entry execution happens on bar i+1 open (next-bar-open logic)
3. Spread is applied adversely on entry (long pays ask, short gets bid)
4. Slippage is applied adversely on entry
5. Commission is charged on entry and exit (round-trip)
6. Exit checks happen on the same bar as entry and subsequent bars
7. Within a bar, we check open first, then high/low
8. If both SL and TP are touched in the same bar, SL fills first (pessimistic assumption)
9. Slippage is applied adversely on SL fills, not on TP fills

COST APPLICATION:
- Spread: applied once on entry (long: +spread/2, short: -spread/2)
- Slippage: applied adversely on entry and SL fills (in pips)
- Commission: applied on entry and exit (round-trip, typically in base currency)

SINGLE POSITION LOGIC:
- Only one position can be open at a time
- New signals are ignored while a position is open
- Position must be closed before a new one can be opened
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import sys

# Import risk_manager for position sizing
sys.path.insert(0, str(Path(__file__).parent))
from risk_manager import calculate_position_size, check_risk_constraints


def run_backtest(df: pd.DataFrame, config: Dict, window_label: str) -> Dict[str, Any]:
    """
    Run deterministic backtest on validated signal dataframe.
    
    Args:
        df: DataFrame with validated signals, sl_price, tp_price columns
        config: full config dict
        window_label: 'train' or 'validation'
        
    Returns:
        dict with:
            - trades: list of trade records
            - equity_curve: list of dicts with time/equity
            - drawdown_curve: list of dicts with time/drawdown
            - fill_stats: dict with fill counts
            - sizing_stats: dict with sizing info
            - risk_halt_flags: dict with halt reasons if triggered
            - meta dict with run info
    """
    
    # Extract config parameters
    symbol = config['backtest']['symbol']
    capital = config['backtest']['capital']
    spread_pips = config['backtest']['spread']
    commission = config['backtest']['commission']
    slippage_pips = config['backtest']['slippage_pips']
    
    # Initialize state
    equity = capital
    peak_equity = capital
    position = None
    trades = []
    equity_curve = []
    drawdown_curve = []
    
    # Risk management state
    daily_loss = 0.0
    daily_loss_reset_date = None
    risk_halted = False
    risk_halt_reason = None
    
    # Counters
    fill_counts = {
        'entries': 0,
        'sl_fills': 0,
        'tp_fills': 0,
        'ignored_signals': 0
    }
    
    sizing_stats = {
        'total_risk_allocated': 0.0,
        'avg_position_size': 0.0,
        'max_position_size': 0.0,
        'min_position_size': float('inf'),
        'sizing_decisions': []
    }
    
    # Convert DataFrame to list of records for iteration
    df_reset = df.reset_index(drop=False)
    bars = df_reset.to_dict('records')
    
    # Iterate through bars
    for i in range(len(bars)):
        current_bar = bars[i]
        current_time = current_bar['time']
        current_signal = current_bar['signal']
        
        # Record equity and drawdown at bar open
        equity_curve.append({'time': current_time, 'equity': equity})
        
        drawdown = (equity - peak_equity) / peak_equity if peak_equity > 0 else 0.0
        drawdown_curve.append({'time': current_time, 'drawdown': drawdown})
        
        # Update peak equity
        if equity > peak_equity:
            peak_equity = equity
        
        # Check daily loss reset
        current_date = pd.Timestamp(current_time).date()
        if daily_loss_reset_date is None or current_date != daily_loss_reset_date:
            daily_loss = 0.0
            daily_loss_reset_date = current_date
        
        # Check if already risk halted
        if risk_halted:
            continue
        
        # Check for exit if position is open
        if position is not None:
            exit_result = check_exit(position, current_bar, spread_pips, commission, slippage_pips)
            
            if exit_result is not None:
                trade_record = close_position(position, exit_result, current_time, equity)
                trades.append(trade_record)
                equity += trade_record['pnl']
                
                if trade_record['pnl'] < 0:
                    daily_loss += abs(trade_record['pnl'])
                
                if exit_result['reason'] == 'sl':
                    fill_counts['sl_fills'] += 1
                elif exit_result['reason'] == 'tp':
                    fill_counts['tp_fills'] += 1
                
                position = None
                
                # Check risk constraints after trade
                max_daily_loss = config['risk']['constraints']['max_daily_loss_pct'] / 100.0
                max_drawdown_halt = config['risk']['constraints']['max_drawdown_halt_pct'] / 100.0
                
                if daily_loss / capital >= max_daily_loss:
                    risk_halted = True
                    risk_halt_reason = 'max_daily_loss_exceeded'
                    continue
                
                current_drawdown = (equity - peak_equity) / peak_equity if peak_equity > 0 else 0.0
                if current_drawdown <= -max_drawdown_halt:
                    risk_halted = True
                    risk_halt_reason = 'max_drawdown_halt_exceeded'
                    continue
        
        # Check for entry signal
        if position is None and current_signal != 0 and i + 1 < len(bars):
            next_bar = bars[i + 1]
            performance_state = build_performance_state(trades)
            
            constraints_ok = check_risk_constraints(
                equity=equity,
                open_positions=0,
                config=config,
                state={
                    'daily_loss': daily_loss,
                    'daily_loss_pct': daily_loss / capital if capital > 0 else 0.0,
                    'current_drawdown': (equity - peak_equity) / peak_equity if peak_equity > 0 else 0.0,
                    **performance_state
                }
            )
            
            if not constraints_ok:
                fill_counts['ignored_signals'] += 1
                continue
            
            signal_row = {
                'signal': current_signal,
                'sl_price': current_bar['sl_price'],
                'tp_price': current_bar['tp_price'],
                'close': current_bar['close'],
                'atr': current_bar.get('atr', None)
            }
            
            sizing_result = calculate_position_size(signal_row, equity, config, performance_state)
            
            if not sizing_result['allowed']:
                fill_counts['ignored_signals'] += 1
                continue
            
            position = enter_position(
                signal=current_signal,
                entry_bar=next_bar,
                signal_bar=current_bar,
                sizing_result=sizing_result,
                spread_pips=spread_pips,
                commission=commission,
                slippage_pips=slippage_pips,
                config=config
            )
            
            fill_counts['entries'] += 1
            sizing_stats['total_risk_allocated'] += sizing_result['risk_amount']
            sizing_stats['max_position_size'] = max(sizing_stats['max_position_size'], sizing_result['size'])
            sizing_stats['min_position_size'] = min(sizing_stats['min_position_size'], sizing_result['size'])
            sizing_stats['sizing_decisions'].append({
                'time': next_bar['time'],
                'size': sizing_result['size'],
                'risk_pct': sizing_result['risk_pct'],
                'model': sizing_result['model_used']
            })
        elif position is None and current_signal != 0:
            fill_counts['ignored_signals'] += 1
    
    # Close remaining position
    if position is not None:
        last_bar = bars[-1]
        exit_result = {'price': last_bar['close'], 'reason': 'end_of_data'}
        trade_record = close_position(position, exit_result, last_bar['time'], equity)
        trades.append(trade_record)
        equity += trade_record['pnl']
    
    # Finalize sizing stats
    if sizing_stats['sizing_decisions']:
        sizing_stats['avg_position_size'] = np.mean([s['size'] for s in sizing_stats['sizing_decisions']])
    else:
        sizing_stats['avg_position_size'] = 0.0
    
    if sizing_stats['min_position_size'] == float('inf'):
        sizing_stats['min_position_size'] = 0.0
    
    return {
        'trades': trades,
        'equity_curve': equity_curve,
        'drawdown_curve': drawdown_curve,
        'fill_stats': fill_counts,
        'sizing_stats': sizing_stats,
        'risk_halt_flags': {'halted': risk_halted, 'reason': risk_halt_reason},
        'metadata': {
            'window_label': window_label,
            'symbol': symbol,
            'initial_capital': capital,
            'final_equity': equity,
            'num_trades': len(trades),
            'num_bars': len(bars)
        }
    }


def enter_position(signal: int, entry_bar: dict, signal_bar: dict, sizing_result: dict, 
                   spread_pips: float, commission: float, slippage_pips: float, config: dict) -> dict:
    """Enter a position on the entry_bar open with costs applied."""
    entry_price = entry_bar['open']
    side = 'long' if signal == 1 else 'short'
    
    # Apply spread and slippage
    if side == 'long':
        entry_price += (spread_pips + slippage_pips) / 10000.0
    else:
        entry_price -= (spread_pips + slippage_pips) / 10000.0
    
    return {
        'trade_id': None,
        'side': side,
        'entry_time': entry_bar['time'],
        'entry_price': entry_price,
        'sl_price': signal_bar['sl_price'],
        'tp_price': signal_bar['tp_price'],
        'size': sizing_result['size'],
        'risk_pct': sizing_result['risk_pct'],
        'risk_amount': sizing_result['risk_amount'],
        'entry_commission': commission,
        'entry_session': signal_bar.get('session', 'unknown'),
        'feature_tags': {k: signal_bar[k] for k in signal_bar.keys() 
                        if k.startswith('feat_') or k in ['trend_up', 'trend_down', 'bullish_engulfing', 'bearish_engulfing']},
        'sizing_model': sizing_result['model_used']
    }


def check_exit(position: dict, current_bar: dict, spread_pips: float, 
               commission: float, slippage_pips: float) -> Optional[dict]:
    """Check if position should be exited. Returns exit_result dict or None."""
    side = position['side']
    sl_price = position['sl_price']
    tp_price = position['tp_price']
    
    sl_hit = False
    tp_hit = False
    
    if side == 'long':
        if current_bar['low'] <= sl_price:
            sl_hit = True
        if current_bar['high'] >= tp_price:
            tp_hit = True
    else:
        if current_bar['high'] >= sl_price:
            sl_hit = True
        if current_bar['low'] <= tp_price:
            tp_hit = True
    
    # Pessimistic: if both hit, SL fills first
    if sl_hit:
        exit_price = sl_price
        # Apply slippage on SL
        if side == 'long':
            exit_price -= slippage_pips / 10000.0
        else:
            exit_price += slippage_pips / 10000.0
        return {'price': exit_price, 'reason': 'sl'}
    elif tp_hit:
        return {'price': tp_price, 'reason': 'tp'}
    
    return None


def close_position(position: dict, exit_result: dict, exit_time, current_equity: float) -> dict:
    """Close position and return trade record."""
    entry_price = position['entry_price']
    exit_price = exit_result['price']
    size = position['size']
    side = position['side']
    
    # Calculate PnL
    if side == 'long':
        price_diff = exit_price - entry_price
    else:
        price_diff = entry_price - exit_price
    
    # PnL in pips then convert to currency
    pnl_pips = price_diff * 10000.0
    pnl_per_lot = price_diff * 100000.0  # Standard lot value
    pnl = pnl_per_lot * size
    
    # Subtract commissions
    total_commission = position['entry_commission'] * 2  # Round-trip
    pnl -= total_commission
    
    # Calculate returns
    pnl_pct = (pnl / current_equity) * 100 if current_equity > 0 else 0.0
    
    # Calculate R-multiple
    risk_amount = position['risk_amount']
    r_multiple = pnl / risk_amount if risk_amount > 0 else 0.0
    
    # Calculate bars held
    entry_time = pd.Timestamp(position['entry_time'])
    exit_time_ts = pd.Timestamp(exit_time)
    bars_held = (exit_time_ts - entry_time).total_seconds() / 3600  # Assuming H1 timeframe
    
    return {
        'trade_id': len([]),  # Will be set by caller
        'side': side,
        'entry_time': position['entry_time'],
        'exit_time': exit_time,
        'entry_price': entry_price,
        'exit_price': exit_price,
        'sl_price': position['sl_price'],
        'tp_price': position['tp_price'],
        'size': size,
        'risk_pct': position['risk_pct'],
        'risk_amount': risk_amount,
        'pnl': pnl,
        'pnl_pct': pnl_pct,
        'r_multiple': r_multiple,
        'bars_held': bars_held,
        'entry_session': position['entry_session'],
        'exit_reason': exit_result['reason'],
        'feature_tags': position['feature_tags']
    }


def build_performance_state(trades: List[dict]) -> dict:
    """Build performance state from recent trades for adaptive sizing."""
    if not trades:
        return {
            'num_trades': 0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'payoff_ratio': 0.0
        }
    
    recent_trades = trades[-50:] if len(trades) > 50 else trades
    wins = [t['pnl'] for t in recent_trades if t['pnl'] > 0]
    losses = [t['pnl'] for t in recent_trades if t['pnl'] < 0]
    
    num_wins = len(wins)
    num_losses = len(losses)
    total_trades = len(recent_trades)
    
    win_rate = num_wins / total_trades if total_trades > 0 else 0.0
    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = abs(np.mean(losses)) if losses else 0.0
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0
    
    return {
        'num_trades': total_trades,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'payoff_ratio': payoff_ratio
    }
