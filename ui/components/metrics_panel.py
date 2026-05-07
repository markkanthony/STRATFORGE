"""
ui/components/metrics_panel.py

Builds the metrics stat-card panel from a metrics dict.
Returns a dbc.Row that can be dropped anywhere in the layout.
"""

import dash_bootstrap_components as dbc
from dash import html


def _fmt(val, precision=2, pct=False, dollar=False):
    """Format a numeric value nicely."""
    if val is None or val != val:  # None or NaN
        return "—"
    if pct:
        return f"{val * 100:.{precision}f}%"
    if dollar:
        return f"${val:,.{precision}f}"
    return f"{val:.{precision}f}"


def _stat_row(label: str, value: str) -> dbc.ListGroupItem:
    return dbc.ListGroupItem(
        [
            html.Span(label, className="text-muted small"),
            html.Span(value, className="float-end fw-semibold small"),
        ],
        style={"padding": "4px 10px", "background": "transparent", "border": "none"},
    )


def _card(title: str, rows: list) -> dbc.Card:
    return dbc.Card(
        [
            dbc.CardHeader(
                title,
                style={
                    "fontSize": "11px",
                    "fontWeight": "700",
                    "letterSpacing": "0.08em",
                    "textTransform": "uppercase",
                    "padding": "6px 10px",
                    "background": "#1e222d",
                    "borderBottom": "1px solid #2a2e39",
                },
            ),
            dbc.CardBody(
                dbc.ListGroup(rows, flush=True),
                style={"padding": "4px 0"},
            ),
        ],
        style={
            "marginBottom": "8px",
            "background": "#161a25",
            "border": "1px solid #2a2e39",
        },
    )


def build_metrics_column(metrics: dict, window_label: str) -> dbc.Col:
    """Build one column of metric cards for a given window (train or validation)."""

    perf = metrics.get("performance", {})
    risk = metrics.get("risk", {})
    trades = metrics.get("trades", {})
    streaks = metrics.get("streaks", {})
    side = metrics.get("side_breakdown", {})

    label_color = "#26a69a" if window_label == "validation" else "#f9a825"

    header = html.Div(
        window_label.upper(),
        style={
            "color": label_color,
            "fontWeight": "700",
            "fontSize": "12px",
            "letterSpacing": "0.1em",
            "marginBottom": "8px",
        },
    )

    perf_card = _card(
        "Performance",
        [
            _stat_row("Sharpe", _fmt(perf.get("sharpe"))),
            _stat_row("Sortino", _fmt(perf.get("sortino"))),
            _stat_row("Calmar", _fmt(perf.get("calmar"))),
            _stat_row("Total Return", _fmt(perf.get("total_return"), pct=True)),
            _stat_row("Ann. Return", _fmt(perf.get("annualized_return"), pct=True)),
        ],
    )

    risk_card = _card(
        "Risk",
        [
            _stat_row("Max Drawdown", _fmt(risk.get("max_drawdown"), pct=True)),
            _stat_row("Avg Drawdown", _fmt(risk.get("avg_drawdown"), pct=True)),
            _stat_row("Ulcer Index", _fmt(risk.get("ulcer_index"))),
            _stat_row("Recovery Factor", _fmt(risk.get("recovery_factor"))),
            _stat_row("DD Duration (bars)", str(risk.get("max_drawdown_duration_bars") or "—")),
        ],
    )

    trades_card = _card(
        "Trades",
        [
            _stat_row("# Trades", str(trades.get("num_trades") or "—")),
            _stat_row("Win Rate", _fmt(trades.get("win_rate"), pct=True)),
            _stat_row("Profit Factor", _fmt(trades.get("profit_factor"))),
            _stat_row("Expectancy", _fmt(trades.get("expectancy"), dollar=True)),
            _stat_row("Avg R-Multiple", _fmt(trades.get("avg_r_multiple"))),
            _stat_row("Avg Win", _fmt(trades.get("avg_win"), dollar=True)),
            _stat_row("Avg Loss", _fmt(trades.get("avg_loss"), dollar=True)),
            _stat_row("Payoff Ratio", _fmt(trades.get("payoff_ratio"))),
        ],
    )

    streaks_card = _card(
        "Streaks",
        [
            _stat_row("Max Win Streak", str(streaks.get("max_consecutive_wins") or "—")),
            _stat_row("Max Loss Streak", str(streaks.get("max_consecutive_losses") or "—")),
        ],
    )

    side_card = _card(
        "Long vs Short",
        [
            _stat_row("Long Trades", str(side.get("long_trades") or "—")),
            _stat_row("Short Trades", str(side.get("short_trades") or "—")),
            _stat_row("Long Win Rate", _fmt(side.get("long_win_rate"), pct=True)),
            _stat_row("Short Win Rate", _fmt(side.get("short_win_rate"), pct=True)),
            _stat_row("Long PF", _fmt(side.get("long_profit_factor"))),
            _stat_row("Short PF", _fmt(side.get("short_profit_factor"))),
        ],
    )

    return dbc.Col(
        [header, perf_card, risk_card, trades_card, streaks_card, side_card],
        width=6,
        style={"paddingRight": "8px"},
    )


def build_metrics_panel(run_data: dict) -> html.Div:
    """
    Build the full Train | Validation metrics panel from run_data.
    Returns an html.Div ready to embed in the layout.
    """
    if not run_data:
        return html.Div(
            "Select a run to view metrics.",
            className="text-muted small",
            style={"padding": "16px"},
        )

    train_metrics = run_data.get("train", {}).get("metrics", {})
    val_metrics = run_data.get("validation", {}).get("metrics", {})

    return html.Div(
        [
            html.Hr(style={"borderColor": "#2a2e39", "margin": "8px 0"}),
            html.Div(
                "Metrics",
                style={
                    "fontSize": "11px",
                    "fontWeight": "700",
                    "letterSpacing": "0.1em",
                    "textTransform": "uppercase",
                    "color": "#758696",
                    "marginBottom": "8px",
                },
            ),
            dbc.Row(
                [
                    build_metrics_column(train_metrics, "train"),
                    build_metrics_column(val_metrics, "validation"),
                ],
                className="g-2",
            ),
        ],
        style={"padding": "0 8px 16px"},
    )
