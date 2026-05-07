"""
ui/pages/dashboard.py

Runs Dashboard: history table + Sharpe bar chart + risk-return scatter.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dash_table
import dash_bootstrap_components as dbc

from ui.data.loader import load_history

# ------------------------------------------------------------------ #
# Table                                                                #
# ------------------------------------------------------------------ #

_TABLE_COLUMNS = [
    {"name": "Run",          "id": "run",           "type": "numeric"},
    {"name": "Date",         "id": "date",          "type": "text"},
    {"name": "Symbol",       "id": "symbol",        "type": "text"},
    {"name": "Val Sharpe",   "id": "val_sharpe",    "type": "numeric", "format": {"specifier": ".3f"}},
    {"name": "Val Return",   "id": "val_return",    "type": "numeric", "format": {"specifier": ".2%"}},
    {"name": "Val DD",       "id": "val_drawdown",  "type": "numeric", "format": {"specifier": ".2%"}},
    {"name": "Val Trades",   "id": "val_trades",    "type": "numeric"},
    {"name": "Train Sharpe", "id": "train_sharpe",  "type": "numeric", "format": {"specifier": ".3f"}},
]

_TABLE_STYLE = dict(
    style_table={
        "overflowX": "auto",
        "borderRadius": "6px",
        "border": "1px solid #2a2e39",
    },
    style_header={
        "backgroundColor": "#1e222d",
        "color": "#d1d4dc",
        "fontWeight": "700",
        "fontSize": "12px",
        "border": "1px solid #2a2e39",
        "padding": "8px 12px",
    },
    style_cell={
        "backgroundColor": "#131722",
        "color": "#d1d4dc",
        "fontSize": "13px",
        "border": "1px solid #1e222d",
        "padding": "8px 12px",
        "fontFamily": "monospace",
    },
    style_data_conditional=[
        {
            "if": {"filter_query": "{val_sharpe} > 0"},
            "color": "#26a69a",
        },
        {
            "if": {"filter_query": "{val_sharpe} < 0"},
            "color": "#ef5350",
        },
        {
            "if": {"state": "selected"},
            "backgroundColor": "#2962ff22",
            "border": "1px solid #2962ff",
        },
        {
            "if": {"state": "active"},
            "backgroundColor": "#2962ff22",
            "border": "1px solid #2962ff",
        },
    ],
)


def _build_table(history: list) -> dash_table.DataTable:
    rows = []
    for h in history:
        ts = h.get("timestamp", "")[:10]
        rows.append({
            "run": h.get("run"),
            "date": ts,
            "symbol": h.get("symbol", ""),
            "val_sharpe": h.get("val_sharpe"),
            "val_return": h.get("val_return"),
            "val_drawdown": h.get("val_drawdown"),
            "val_trades": h.get("val_trades"),
            "train_sharpe": h.get("train_sharpe"),
        })

    return dash_table.DataTable(
        id="dashboard-runs-table",
        columns=_TABLE_COLUMNS,
        data=rows,
        sort_action="native",
        row_selectable="single",
        selected_rows=[0] if rows else [],
        page_size=20,
        **_TABLE_STYLE,
    )


# ------------------------------------------------------------------ #
# Charts                                                               #
# ------------------------------------------------------------------ #

_DARK_BG = "#131722"
_PANEL_BG = "#161a25"
_GRID = "#1e222d"


def _build_sharpe_chart(history: list) -> go.Figure:
    runs = [h["run"] for h in history]
    train_sharpes = [h.get("train_sharpe") for h in history]
    val_sharpes = [h.get("val_sharpe") for h in history]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=runs, y=train_sharpes,
        name="Train Sharpe",
        marker_color="#f9a825",
        opacity=0.85,
    ))
    fig.add_trace(go.Bar(
        x=runs, y=val_sharpes,
        name="Val Sharpe",
        marker_color="#26a69a",
        opacity=0.85,
    ))
    fig.add_hline(y=0, line_color="#758696", line_width=1)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=_PANEL_BG,
        plot_bgcolor=_DARK_BG,
        title=dict(text="Sharpe Ratio by Run", font=dict(size=13, color="#d1d4dc")),
        barmode="group",
        legend=dict(orientation="h", y=1.1),
        xaxis=dict(title="Run #", gridcolor=_GRID, tickmode="linear", tick0=1, dtick=1),
        yaxis=dict(title="Sharpe", gridcolor=_GRID, zeroline=False),
        margin=dict(l=50, r=20, t=50, b=40),
        height=300,
    )
    return fig


def _build_riskreturn_chart(history: list) -> go.Figure:
    runs = [h["run"] for h in history]
    drawdowns = [h.get("val_drawdown") for h in history]
    returns = [h.get("val_return") for h in history]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=drawdowns,
        y=returns,
        mode="markers+text",
        text=[f"#{r}" for r in runs],
        textposition="top center",
        marker=dict(
            size=12,
            color=[h.get("val_sharpe", 0) for h in history],
            colorscale=[[0, "#ef5350"], [0.5, "#758696"], [1, "#26a69a"]],
            colorbar=dict(title="Sharpe", thickness=12),
            showscale=True,
            line=dict(color="#ffffff", width=1),
        ),
        hovertemplate=(
            "Run #%{text}<br>"
            "DD: %{x:.1%}<br>"
            "Return: %{y:.1%}<br>"
            "<extra></extra>"
        ),
    ))
    fig.add_vline(x=0, line_color="#758696", line_width=1, line_dash="dot")
    fig.add_hline(y=0, line_color="#758696", line_width=1, line_dash="dot")
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=_PANEL_BG,
        plot_bgcolor=_DARK_BG,
        title=dict(text="Risk-Return (Validation)", font=dict(size=13, color="#d1d4dc")),
        xaxis=dict(title="Max Drawdown", tickformat=".1%", gridcolor=_GRID),
        yaxis=dict(title="Total Return", tickformat=".1%", gridcolor=_GRID),
        margin=dict(l=60, r=20, t=50, b=50),
        height=300,
    )
    return fig


# ------------------------------------------------------------------ #
# Page builder                                                          #
# ------------------------------------------------------------------ #

def build_dashboard_layout() -> html.Div:
    """Return the complete Dashboard page layout."""
    import plotly.io as pio
    from dash import dcc

    history = load_history()

    if not history:
        return html.Div(
            [
                html.H5("No runs found", className="text-muted mt-4"),
                html.P("Run python run.py to generate your first backtest.", className="text-muted"),
            ],
            style={"padding": "24px"},
        )

    return html.Div(
        [
            html.H5(
                "Backtest Runs",
                style={"color": "#d1d4dc", "marginBottom": "12px", "fontWeight": "700"},
            ),
            html.Div(
                _build_table(history),
                style={"marginBottom": "24px"},
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Graph(
                            figure=_build_sharpe_chart(history),
                            config={"displayModeBar": False},
                        ),
                        width=7,
                    ),
                    dbc.Col(
                        dcc.Graph(
                            figure=_build_riskreturn_chart(history),
                            config={"displayModeBar": False},
                        ),
                        width=5,
                    ),
                ],
                className="g-3",
            ),
        ],
        style={"padding": "16px"},
    )
