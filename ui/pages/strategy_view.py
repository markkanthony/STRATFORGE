"""
ui/pages/strategy_view.py — Read-only display of the strategy configuration.

Reads config.yaml and renders strategy mode, indicators, patterns,
context filters, entry rules, and exit settings.
"""

from dash import html
import dash_bootstrap_components as dbc

from ui.data.projects import load_config

_CARD   = "#161d2f"
_BORDER = "#1e2d47"
_BLUE   = "#3b82f6"
_TEAL   = "#14b8a6"
_RED    = "#ef4444"
_AMBER  = "#f59e0b"
_TEXT   = "#e2e8f0"
_MUTED  = "#64748b"
_GREEN  = "#22c55e"


def _badge(text: str, color: str) -> html.Span:
    return html.Span(text, style={
        "fontSize": "10px",
        "fontWeight": "700",
        "letterSpacing": "0.07em",
        "textTransform": "uppercase",
        "padding": "3px 8px",
        "borderRadius": "4px",
        "background": f"{color}1a",
        "color": color,
        "border": f"1px solid {color}33",
    })


def _check(enabled: bool) -> html.Span:
    return html.Span(
        "✓ ON" if enabled else "✗ OFF",
        style={"color": _GREEN if enabled else _RED, "fontWeight": "600", "fontSize": "12px", "fontFamily": "monospace"},
    )


def _kv_row(label: str, value, mono: bool = True) -> html.Div:
    val_style = {
        "fontSize": "13px",
        "fontWeight": "600",
        "color": _TEXT,
    }
    if mono:
        val_style["fontFamily"] = "monospace"

    return html.Div([
        html.Span(label, style={"fontSize": "12px", "color": _MUTED}),
        html.Span(str(value), style=val_style) if not isinstance(value, html.Span) else value,
    ], style={
        "display": "flex",
        "justifyContent": "space-between",
        "alignItems": "center",
        "padding": "6px 0",
        "borderBottom": f"1px solid {_BORDER}",
    })


def _section(title: str, content) -> html.Div:
    return html.Div([
        html.Div(title, style={
            "fontSize": "10px",
            "letterSpacing": "0.1em",
            "textTransform": "uppercase",
            "fontWeight": "700",
            "color": _MUTED,
            "marginBottom": "12px",
        }),
        content,
    ], style={
        "background": _CARD,
        "border": f"1px solid {_BORDER}",
        "borderRadius": "8px",
        "padding": "18px 20px",
    })


def _condition_list(conditions: list) -> html.Div:
    if not conditions:
        return html.Div("—", style={"color": _MUTED, "fontSize": "12px"})
    return html.Div([
        html.Div([
            html.Span("▸ ", style={"color": _BLUE}),
            html.Code(c, style={"fontSize": "12px", "color": _TEXT, "background": "none"}),
        ], style={"padding": "3px 0"})
        for c in conditions
    ])


def build_strategy_content() -> html.Div:
    """Return the strategy configuration section."""
    config   = load_config()
    strategy = config.get("strategy", {})
    bt       = config.get("backtest", {})
    windows  = config.get("windows", {})

    mode       = strategy.get("mode", "—")
    indicators = strategy.get("indicators", {})
    patterns   = strategy.get("patterns", {})
    context    = strategy.get("context", {})
    entry      = strategy.get("entry", {})
    exits      = strategy.get("exits", {})

    mode_color = {"indicator": _BLUE, "pattern": _AMBER, "hybrid": _TEAL}.get(mode, _MUTED)

    return html.Div([
        # Page header
        html.Div([
            html.H5("Strategy Configuration", style={"color": _TEXT, "fontWeight": "700", "fontSize": "15px", "margin": 0}),
            _badge(mode, mode_color),
        ], style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "marginBottom": "20px",
            "paddingBottom": "14px",
            "borderBottom": f"1px solid {_BORDER}",
        }),

        dbc.Row([
            # ── Column 1: Backtest setup + Indicators ────────── #
            dbc.Col([
                _section("Backtest Setup", html.Div([
                    _kv_row("Symbol",     bt.get("symbol", "—")),
                    _kv_row("Timeframe",  bt.get("timeframe", "—")),
                    _kv_row("Capital",    f"${bt.get('capital', 0):,}"),
                    _kv_row("Spread",     f"{bt.get('spread', '—')} pips"),
                    _kv_row("Commission", f"${bt.get('commission', '—')}"),
                    _kv_row("Slippage",   f"{bt.get('slippage_pips', '—')} pips"),
                ])),

                html.Div(style={"height": "16px"}),

                _section("Indicators", html.Div([
                    _kv_row("Fast EMA",   indicators.get("fast_ema", "—")),
                    _kv_row("Slow EMA",   indicators.get("slow_ema", "—")),
                    _kv_row("RSI Period", indicators.get("rsi_period", "—")),
                    _kv_row("ATR Period", indicators.get("atr_period", "—")),
                ])),

                html.Div(style={"height": "16px"}),

                _section("Windows", html.Div([
                    _kv_row("Train Start",      windows.get("train_start", "—")),
                    _kv_row("Train End",        windows.get("train_end", "—")),
                    _kv_row("Validation Start", windows.get("validation_start", "—")),
                    _kv_row("Validation End",   windows.get("validation_end", "—")),
                ])),
            ], width=4),

            # ── Column 2: Patterns + Context ─────────────────── #
            dbc.Col([
                _section("Patterns", html.Div([
                    _kv_row("Bullish Engulfing",  _check(patterns.get("bullish_engulfing", False))),
                    _kv_row("Bearish Engulfing",  _check(patterns.get("bearish_engulfing", False))),
                    _kv_row("Inside Bar Breakout", _check(patterns.get("inside_bar_breakout", False))),
                    _kv_row("Sweep Prev High",    _check(patterns.get("sweep_prev_high", False))),
                    _kv_row("Sweep Prev Low",     _check(patterns.get("sweep_prev_low", False))),
                    _kv_row("ORB",                _check((patterns.get("orb") or {}).get("enabled", False))),
                    _kv_row("ORB Bars",           (patterns.get("orb") or {}).get("bars", "—")),
                ])),

                html.Div(style={"height": "16px"}),

                _section("Context Filters", html.Div([
                    _kv_row("Prev-Day Levels", _check(context.get("use_prev_day_levels", False))),
                    _kv_row("Session Filter",  _check(context.get("use_session_filter", False))),
                    _kv_row("Trend Filter",    context.get("trend_filter", "—")),
                ])),
            ], width=4),

            # ── Column 3: Entry rules + Exits ────────────────── #
            dbc.Col([
                _section("Long Entry Rules", _condition_list(entry.get("long_require_all", []))),

                html.Div(style={"height": "16px"}),

                _section("Short Entry Rules", _condition_list(entry.get("short_require_all", []))),

                html.Div(style={"height": "16px"}),

                _section("Exit Settings", html.Div([
                    _kv_row("ATR SL Multiplier", exits.get("atr_sl_multiplier", "—")),
                    _kv_row("ATR TP Multiplier", exits.get("atr_tp_multiplier", "—")),
                ])),
            ], width=4),
        ], className="g-3"),

    ], style={"padding": "24px"})
