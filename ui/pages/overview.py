"""
ui/pages/overview.py — Project overview section.

Shows key metrics from the latest selected run: performance, risk, trade stats.
Content is rebuilt whenever store-run-data changes (see nav_callbacks).
"""

from dash import html
import dash_bootstrap_components as dbc

from ui.data.loader import load_history

# Design tokens (matches home.py palette)
_CARD   = "#161d2f"
_BORDER = "#1e2d47"
_BLUE   = "#3b82f6"
_TEAL   = "#14b8a6"
_RED    = "#ef4444"
_AMBER  = "#f59e0b"
_TEXT   = "#e2e8f0"
_MUTED  = "#64748b"
_DIM    = "#1e2d47"


def _fmt(val, pct=False, dollar=False, precision=2) -> str:
    if val is None or (isinstance(val, float) and val != val):
        return "—"
    if pct:
        return f"{val * 100:+.{precision}f}%"
    if dollar:
        return f"${val:,.{precision}f}"
    return f"{val:.{precision}f}"


def _color_val(val, invert=False) -> str:
    if val is None:
        return _MUTED
    pos = val >= 0
    if invert:
        pos = not pos
    return _TEAL if pos else _RED


def _metric_tile(label: str, value: str, color: str = _TEXT, sub: str = "") -> html.Div:
    return html.Div([
        html.Div(label, style={
            "fontSize": "10px",
            "letterSpacing": "0.08em",
            "textTransform": "uppercase",
            "color": _MUTED,
            "marginBottom": "6px",
        }),
        html.Div(value, style={
            "fontSize": "24px",
            "fontWeight": "700",
            "fontFamily": "'Courier New', monospace",
            "color": color,
            "lineHeight": 1,
        }),
        html.Div(sub, style={"fontSize": "11px", "color": _MUTED, "marginTop": "4px"}) if sub else None,
    ], style={
        "background": _CARD,
        "border": f"1px solid {_BORDER}",
        "borderRadius": "8px",
        "padding": "16px 20px",
        "flex": 1,
        "minWidth": "120px",
    })


def _section_card(title: str, rows: list) -> html.Div:
    return html.Div([
        html.Div(title, style={
            "fontSize": "10px",
            "letterSpacing": "0.1em",
            "textTransform": "uppercase",
            "fontWeight": "700",
            "color": _MUTED,
            "marginBottom": "12px",
        }),
        html.Div(rows),
    ], style={
        "background": _CARD,
        "border": f"1px solid {_BORDER}",
        "borderRadius": "8px",
        "padding": "18px 20px",
    })


def _row(label: str, value: str, color: str = _TEXT) -> html.Div:
    return html.Div([
        html.Span(label, style={"fontSize": "12px", "color": _MUTED}),
        html.Span(value, style={"fontSize": "13px", "fontWeight": "600", "color": color, "fontFamily": "monospace"}),
    ], style={
        "display": "flex",
        "justifyContent": "space-between",
        "padding": "5px 0",
        "borderBottom": f"1px solid {_BORDER}",
    })


def build_overview_content(run_data: dict = None, window: str = "validation") -> html.Div:
    """Build the overview section content from the currently selected run."""
    history = load_history()

    if not run_data:
        return html.Div([
            html.Div([
                html.Div("⚡", style={"fontSize": "32px", "marginBottom": "12px", "color": _BLUE}),
                html.Div("No run selected", style={"fontSize": "16px", "fontWeight": "700", "color": _TEXT, "marginBottom": "8px"}),
                html.Div(
                    "Select a run from the Analysis tab or click Run New Backtest to get started.",
                    style={"fontSize": "13px", "color": _MUTED, "maxWidth": "360px"},
                ),
                html.Div(
                    f"{len(history)} run{'s' if len(history) != 1 else ''} in history" if history else "No runs yet",
                    style={"fontSize": "11px", "color": _MUTED, "marginTop": "16px", "padding": "6px 14px",
                           "border": f"1px solid {_BORDER}", "borderRadius": "4px", "display": "inline-block"},
                ),
            ], style={"textAlign": "center", "paddingTop": "60px"}),
        ])

    w        = window or "validation"
    metrics  = run_data.get(w, {}).get("metrics", {})
    perf     = metrics.get("performance", {})
    risk     = metrics.get("risk", {})
    trades_m = metrics.get("trades", {})
    streaks  = metrics.get("streaks", {})
    side     = metrics.get("side_breakdown", {})

    run_num  = run_data.get("run", "—")
    symbol   = run_data.get("symbol", "—")
    ts       = run_data.get("timestamp", "")[:10]

    sharpe  = perf.get("sharpe")
    ret     = perf.get("total_return")
    dd      = risk.get("max_drawdown")
    pf      = trades_m.get("profit_factor")
    winrate = trades_m.get("win_rate")

    # Overfit gap (train - val)
    train_m  = run_data.get("train", {}).get("metrics", {})
    train_sh = train_m.get("performance", {}).get("sharpe")
    val_sh   = perf.get("sharpe")
    gap_val  = None
    gap_str  = "—"
    if train_sh is not None and val_sh is not None:
        gap_val = train_sh - val_sh
        gap_str = f"{gap_val:.2f}"

    gap_color = _TEAL if (gap_val or 0) < 0.5 else (_AMBER if (gap_val or 0) < 1.0 else _RED)

    win_pct   = (winrate or 0) * 100
    fill_w    = min(win_pct, 100)
    bar_color = _TEAL if win_pct >= 50 else _AMBER

    return html.Div([
        # Run header
        html.Div([
            html.Div([
                html.Span(f"Run #{run_num}", style={"fontWeight": "700", "fontSize": "15px", "color": _TEXT}),
                html.Span(f" · {symbol}", style={"fontSize": "13px", "color": _MUTED}),
            ]),
            html.Div([
                html.Span(ts, style={"fontSize": "12px", "color": _MUTED}),
                html.Span(
                    f"  ·  {w.upper()}",
                    style={"fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.08em",
                           "color": _TEAL if w == "validation" else _AMBER, "marginLeft": "6px"},
                ),
            ]),
        ], style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "marginBottom": "20px",
            "paddingBottom": "14px",
            "borderBottom": f"1px solid {_BORDER}",
        }),

        # ── Top KPI tiles ─────────────────────────────────────── #
        html.Div([
            _metric_tile("Sharpe",   _fmt(sharpe),           _color_val(sharpe),        sub="Validation"),
            _metric_tile("Return",   _fmt(ret, pct=True),    _color_val(ret),            sub="Total"),
            _metric_tile("Max DD",   _fmt(dd, pct=True),     _color_val(dd, invert=True), sub="Drawdown"),
            _metric_tile("P/Factor", _fmt(pf),               _TEAL if (pf or 0) > 1 else _RED, sub="Profit Factor"),
        ], style={"display": "flex", "gap": "12px", "marginBottom": "20px", "flexWrap": "wrap"}),

        # ── Win rate bar ──────────────────────────────────────── #
        html.Div([
            html.Div([
                html.Span("Win Rate", style={"fontSize": "12px", "color": _MUTED}),
                html.Span(f"{win_pct:.1f}%", style={"fontSize": "13px", "fontWeight": "700", "color": bar_color}),
            ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "6px"}),
            html.Div([
                html.Div(style={
                    "width": f"{fill_w:.1f}%",
                    "height": "6px",
                    "background": f"linear-gradient(90deg, {_TEAL}, {_BLUE})",
                    "borderRadius": "3px",
                }),
            ], style={"background": _BORDER, "height": "6px", "borderRadius": "3px", "overflow": "hidden"}),
        ], style={
            "background": _CARD,
            "border": f"1px solid {_BORDER}",
            "borderRadius": "8px",
            "padding": "14px 20px",
            "marginBottom": "20px",
        }),

        # ── Detail cards ──────────────────────────────────────── #
        dbc.Row([
            dbc.Col(_section_card("Performance", [
                _row("Sharpe",       _fmt(sharpe),                    _color_val(sharpe)),
                _row("Sortino",      _fmt(perf.get("sortino")),       _color_val(perf.get("sortino"))),
                _row("Calmar",       _fmt(perf.get("calmar")),        _color_val(perf.get("calmar"))),
                _row("Ann. Return",  _fmt(perf.get("annualized_return"), pct=True), _color_val(perf.get("annualized_return"))),
                _row("Train Sharpe", _fmt(train_sh),                  _color_val(train_sh)),
                _row("Overfit Gap",  gap_str,                          gap_color),
            ]), width=4),

            dbc.Col(_section_card("Risk", [
                _row("Max Drawdown",  _fmt(dd, pct=True),                            _RED),
                _row("Avg Drawdown",  _fmt(risk.get("avg_drawdown"), pct=True),      _MUTED),
                _row("Ulcer Index",   _fmt(risk.get("ulcer_index"))),
                _row("Recovery Factor", _fmt(risk.get("recovery_factor"))),
                _row("DD Duration",   str(risk.get("max_drawdown_duration_bars") or "—") + " bars"),
            ]), width=4),

            dbc.Col(_section_card("Trades", [
                _row("# Trades",      str(trades_m.get("num_trades") or "—")),
                _row("Win Rate",      _fmt(winrate, pct=True),           bar_color),
                _row("Profit Factor", _fmt(pf),                          _TEAL if (pf or 0) > 1 else _RED),
                _row("Expectancy",    _fmt(trades_m.get("expectancy"), dollar=True)),
                _row("Avg R-Multiple", _fmt(trades_m.get("avg_r_multiple"))),
                _row("Payoff Ratio",  _fmt(trades_m.get("payoff_ratio"))),
            ]), width=4),
        ], className="g-3"),

    ], style={"padding": "24px"})
