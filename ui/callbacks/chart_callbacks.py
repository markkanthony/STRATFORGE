"""
ui/callbacks/chart_callbacks.py

Callbacks for the Chart tab:
  1. Build/refresh the candlestick figure when run-data or window changes
  2. Zoom x-axis to highlighted trade on journal click
"""

import pandas as pd
from dash import Input, Output, State, no_update

from ui.data.loader import load_ohlcv_for_run, get_trades, get_equity
from ui.pages.chart import build_chart_figure, build_empty_chart


def register(app):

    # ---- Main chart builder ---------------------------------------- #
    @app.callback(
        Output("main-chart", "figure"),
        Input("store-run-data", "data"),
        Input("store-selected-window", "data"),
        Input("store-highlighted-trade-idx", "data"),
    )
    def update_chart(run_data, window, highlighted_idx):
        if not run_data:
            return build_empty_chart()

        window = window or "validation"
        symbol = run_data.get("symbol", "")

        ohlcv = load_ohlcv_for_run(run_data, window)
        trades = get_trades(run_data, window)
        equity = get_equity(run_data, window)

        fig = build_chart_figure(
            ohlcv=ohlcv,
            trades=trades,
            equity=equity,
            highlighted_idx=highlighted_idx,
            symbol=symbol,
            window_label=window,
        )

        # If a trade is highlighted, zoom the x-axis to ±10 bars around it
        if highlighted_idx is not None and trades:
            ht = next((t for t in trades if t.get("trade_idx") == highlighted_idx), None)
            if ht and not ohlcv.empty:
                try:
                    entry_t = pd.to_datetime(ht["entry_time"], utc=True)
                    exit_t  = pd.to_datetime(ht["exit_time"],  utc=True)

                    # Find bar index of entry
                    ohlcv_times = pd.to_datetime(ohlcv["time"], utc=True)
                    idx_before = ohlcv_times[ohlcv_times <= entry_t].index
                    idx_after  = ohlcv_times[ohlcv_times >= exit_t].index

                    if len(idx_before) and len(idx_after):
                        bar_start = max(0, idx_before[-1] - 15)
                        bar_end   = min(len(ohlcv) - 1, idx_after[0] + 15)
                        x0 = ohlcv_times.iloc[bar_start]
                        x1 = ohlcv_times.iloc[bar_end]
                        fig.update_xaxes(range=[x0, x1])
                except Exception:
                    pass

        return fig
