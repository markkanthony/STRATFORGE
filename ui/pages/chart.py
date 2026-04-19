"""
ui/pages/chart.py

TradingView-like candlestick chart with trade executions overlaid.

Three-panel subplot (shared x-axis):
  Row 1 (60%): Candlestick + trade entry/exit markers + SL/TP dashed lines
  Row 2 (25%): Equity curve (area fill)
  Row 3 (15%): Volume bars

Trade marker legend:
  Entry long  — green triangle-up
  Entry short — red triangle-down
  Exit TP     — teal star
  Exit SL     — red x
  Exit EOD    — grey circle
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import dcc, html
import dash_bootstrap_components as dbc

# TradingView colour palette
_GREEN  = "#26a69a"
_RED    = "#ef5350"
_BLUE   = "#2962ff"
_GOLD   = "#f9a825"
_GREY   = "#758696"
_BG     = "#131722"
_PANEL  = "#161a25"
_GRID   = "#1e222d"

# Entry marker colours by side
_ENTRY_COLOR = {"long": _GREEN, "short": _RED}
_ENTRY_SYMBOL = {"long": "triangle-up", "short": "triangle-down"}

# Exit marker colours / symbols by exit_reason
_EXIT_COLOR  = {"tp": _GREEN, "sl": _RED,  "end_of_data": _GREY}
_EXIT_SYMBOL = {"tp": "star",  "sl": "x",  "end_of_data": "circle"}


def _parse_time(ts):
    """Parse ISO timestamp string to pandas Timestamp."""
    return pd.to_datetime(ts, utc=True)


def build_chart_figure(
    ohlcv: pd.DataFrame,
    trades: list,
    equity: list,
    highlighted_idx: int | None = None,
    symbol: str = "",
    window_label: str = "",
) -> go.Figure:
    """
    Build and return the full three-panel Plotly figure.

    Args:
        ohlcv:           OHLCV DataFrame (time, open, high, low, close, tick_volume)
        trades:          list of trade dicts (with trade_idx injected)
        equity:          list of {"time": str, "equity": float}
        highlighted_idx: trade_idx to highlight (from journal click)
        symbol:          e.g. "EURUSD"
        window_label:    "train" or "validation"
    """
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.60, 0.25, 0.15],
        vertical_spacing=0.02,
    )

    # ---- Row 1: Candlestick ---------------------------------------- #
    if not ohlcv.empty:
        fig.add_trace(
            go.Candlestick(
                x=ohlcv["time"],
                open=ohlcv["open"],
                high=ohlcv["high"],
                low=ohlcv["low"],
                close=ohlcv["close"],
                name=symbol,
                increasing_line_color=_GREEN,
                decreasing_line_color=_RED,
                increasing_fillcolor=_GREEN,
                decreasing_fillcolor=_RED,
                showlegend=False,
                line=dict(width=1),
                whiskerwidth=0,
            ),
            row=1, col=1,
        )

    # ---- Row 1: SL/TP lines per trade ------------------------------ #
    for t in trades:
        try:
            x0 = _parse_time(t["entry_time"])
            x1 = _parse_time(t["exit_time"])
        except Exception:
            continue

        # SL line
        fig.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[t["sl_price"], t["sl_price"]],
                mode="lines",
                line=dict(color=_RED, width=1, dash="dash"),
                opacity=0.45,
                showlegend=False,
                hoverinfo="skip",
            ),
            row=1, col=1,
        )
        # TP line
        fig.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[t["tp_price"], t["tp_price"]],
                mode="lines",
                line=dict(color=_GREEN, width=1, dash="dash"),
                opacity=0.45,
                showlegend=False,
                hoverinfo="skip",
            ),
            row=1, col=1,
        )

    # ---- Row 1: Trade markers (entries + exits) -------------------- #
    # Group by (side, exit_reason) to minimise trace count
    from itertools import groupby
    from operator import itemgetter

    sides = ["long", "short"]
    reasons = ["tp", "sl", "end_of_data"]

    for side in sides:
        for reason in reasons:
            group = [t for t in trades if t.get("side") == side and t.get("exit_reason") == reason]
            if not group:
                continue

            label = f"{side.capitalize()} ({reason.upper()})"

            # Entry markers
            fig.add_trace(
                go.Scatter(
                    x=[_parse_time(t["entry_time"]) for t in group],
                    y=[t["entry_price"] for t in group],
                    mode="markers",
                    name=f"Entry {label}",
                    marker=dict(
                        symbol=_ENTRY_SYMBOL[side],
                        size=11,
                        color=_ENTRY_COLOR[side],
                        line=dict(color="#ffffff", width=0.8),
                    ),
                    customdata=[
                        [t["pnl"], t["r_multiple"], t["exit_reason"],
                         t["bars_held"], t["side"], t.get("trade_idx", 0)]
                        for t in group
                    ],
                    hovertemplate=(
                        f"<b>ENTRY {side.upper()}</b><br>"
                        "Price: %{y:.5f}<br>"
                        "PnL: $%{customdata[0]:.2f}<br>"
                        "R: %{customdata[1]:.2f}R<br>"
                        "Exit: %{customdata[2]}<br>"
                        "Bars: %{customdata[3]}<br>"
                        "<extra></extra>"
                    ),
                    showlegend=True,
                    legendgroup=f"entry_{side}",
                ),
                row=1, col=1,
            )

            # Exit markers
            fig.add_trace(
                go.Scatter(
                    x=[_parse_time(t["exit_time"]) for t in group],
                    y=[t["exit_price"] for t in group],
                    mode="markers",
                    name=f"Exit {label}",
                    marker=dict(
                        symbol=_EXIT_SYMBOL.get(reason, "circle"),
                        size=9,
                        color=_EXIT_COLOR.get(reason, _GREY),
                        line=dict(color="#ffffff", width=0.8),
                    ),
                    hovertemplate=(
                        f"<b>EXIT {reason.upper()}</b><br>"
                        "Price: %{y:.5f}<br>"
                        "<extra></extra>"
                    ),
                    showlegend=False,
                    legendgroup=f"exit_{side}_{reason}",
                ),
                row=1, col=1,
            )

    # ---- Row 1: Highlighted trade ring ----------------------------- #
    if highlighted_idx is not None:
        ht = next((t for t in trades if t.get("trade_idx") == highlighted_idx), None)
        if ht:
            try:
                fig.add_trace(
                    go.Scatter(
                        x=[_parse_time(ht["entry_time"])],
                        y=[ht["entry_price"]],
                        mode="markers",
                        marker=dict(
                            symbol="circle-open",
                            size=20,
                            color=_GOLD,
                            line=dict(color=_GOLD, width=2.5),
                        ),
                        showlegend=False,
                        hoverinfo="skip",
                        name="highlighted",
                    ),
                    row=1, col=1,
                )
            except Exception:
                pass

    # ---- Row 2: Equity curve --------------------------------------- #
    if equity:
        eq_times = [_parse_time(e["time"]) for e in equity]
        eq_vals = [e["equity"] for e in equity]
        fig.add_trace(
            go.Scatter(
                x=eq_times,
                y=eq_vals,
                mode="lines",
                name="Equity",
                line=dict(color=_BLUE, width=1.5),
                fill="tozeroy",
                fillcolor="rgba(41,98,255,0.10)",
            ),
            row=2, col=1,
        )

    # ---- Row 3: Volume --------------------------------------------- #
    if not ohlcv.empty and "tick_volume" in ohlcv.columns:
        vol_colors = [
            _GREEN if c >= o else _RED
            for c, o in zip(ohlcv["close"], ohlcv["open"])
        ]
        fig.add_trace(
            go.Bar(
                x=ohlcv["time"],
                y=ohlcv["tick_volume"],
                name="Volume",
                marker_color=vol_colors,
                opacity=0.6,
                showlegend=False,
            ),
            row=3, col=1,
        )

    # ---- Layout ---------------------------------------------------- #
    window_str = window_label.capitalize() if window_label else ""
    title_text = f"{symbol}  ·  {window_str} Window" if symbol else "Chart"

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=_BG,
        plot_bgcolor=_BG,
        font=dict(color="#d1d4dc", size=11),
        title=dict(text=title_text, font=dict(size=14, color="#d1d4dc"), x=0.01),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        height=820,
        margin=dict(l=70, r=20, t=50, b=20),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.01,
            xanchor="left", x=0,
            font=dict(size=11),
            bgcolor="rgba(0,0,0,0)",
        ),
    )

    # Shared x-axis grid styling
    for i in range(1, 4):
        xkey = "xaxis" if i == 1 else f"xaxis{i}"
        fig.update_layout(**{
            xkey: dict(
                showgrid=True,
                gridcolor=_GRID,
                showspikes=True,
                spikecolor=_GREY,
                spikethickness=1,
                zeroline=False,
            )
        })

    # Y-axis labels
    fig.update_yaxes(gridcolor=_GRID, zeroline=False)
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Equity ($)", row=2, col=1)
    fig.update_yaxes(title_text="Volume", row=3, col=1)

    return fig


def build_empty_chart() -> go.Figure:
    """Return a placeholder figure when no run is selected."""
    fig = go.Figure()
    fig.add_annotation(
        text="Select a run from the sidebar",
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=16, color=_GREY),
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=_BG,
        plot_bgcolor=_BG,
        height=820,
        margin=dict(l=70, r=20, t=50, b=20),
    )
    return fig


def build_chart_layout() -> html.Div:
    """Return the Chart page layout shell (graph is populated by callback)."""
    return html.Div(
        [
            dcc.Graph(
                id="main-chart",
                figure=build_empty_chart(),
                config={
                    "scrollZoom": True,
                    "displayModeBar": True,
                    "modeBarButtonsToRemove": ["select2d", "lasso2d"],
                    "toImageButtonOptions": {"format": "png", "scale": 2},
                },
                style={"height": "820px"},
            ),
        ],
        style={"padding": "8px"},
    )
