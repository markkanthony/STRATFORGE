"""
ui/pages/risk_view.py — Read-only display of the risk management configuration.
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


def _kv_row(label: str, value: str, color: str = _TEXT) -> html.Div:
    return html.Div([
        html.Span(label, style={"fontSize": "12px", "color": _MUTED}),
        html.Span(str(value), style={"fontSize": "13px", "fontWeight": "600", "color": color, "fontFamily": "monospace"}),
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


def _constraint_bar(label: str, value: float, max_val: float, color: str) -> html.Div:
    pct = min((value / max_val) * 100, 100) if max_val else 0
    return html.Div([
        html.Div([
            html.Span(label, style={"fontSize": "12px", "color": _MUTED}),
            html.Span(f"{value}%", style={"fontSize": "12px", "fontWeight": "600", "color": color, "fontFamily": "monospace"}),
        ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "5px"}),
        html.Div([
            html.Div(style={
                "width": f"{pct:.1f}%",
                "height": "4px",
                "background": color,
                "borderRadius": "2px",
            }),
        ], style={"background": _BORDER, "height": "4px", "borderRadius": "2px", "overflow": "hidden", "marginBottom": "8px"}),
    ])


def build_risk_content() -> html.Div:
    """Return the risk management configuration section."""
    config = load_config()
    risk   = config.get("risk", {})

    model       = risk.get("model", "—")
    constraints = risk.get("constraints", {})
    ff          = risk.get("fixed_fractional", {})
    fl          = risk.get("fixed_lot", {})
    va          = risk.get("volatility_adjusted", {})
    kelly       = risk.get("fractional_kelly", {})

    model_color = {
        "fixed_lot":            _BLUE,
        "fixed_fractional":     _TEAL,
        "volatility_adjusted":  _AMBER,
        "fractional_kelly":     _RED,
    }.get(model, _MUTED)

    model_descriptions = {
        "fixed_lot":           "Fixed position size regardless of account equity or volatility.",
        "fixed_fractional":    "Risk a fixed percentage of account equity per trade.",
        "volatility_adjusted": "Scale position size inversely with ATR-measured volatility.",
        "fractional_kelly":    "Kelly Criterion with a safety fraction cap.",
    }

    max_dd = constraints.get("max_drawdown_halt_pct", 20)
    max_dl = constraints.get("max_daily_loss_pct", 5)
    max_r  = constraints.get("max_open_risk_pct", 2)

    return html.Div([
        # Page header
        html.Div([
            html.H5("Risk Management", style={"color": _TEXT, "fontWeight": "700", "fontSize": "15px", "margin": 0}),
            _badge(model.replace("_", " "), model_color),
        ], style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "marginBottom": "20px",
            "paddingBottom": "14px",
            "borderBottom": f"1px solid {_BORDER}",
        }),

        dbc.Row([
            # ── Column 1: Model + active params ─────────────── #
            dbc.Col([
                _section("Active Model", html.Div([
                    html.Div(_badge(model.replace("_", " "), model_color), style={"marginBottom": "10px"}),
                    html.Div(
                        model_descriptions.get(model, ""),
                        style={"fontSize": "12px", "color": _MUTED, "lineHeight": "1.5", "marginBottom": "12px"},
                    ),
                    html.Hr(style={"borderColor": _BORDER, "margin": "8px 0"}),
                    # Active model params
                    *([
                        _kv_row("Risk per Trade", f"{ff.get('risk_pct', '—')}%"),
                    ] if model == "fixed_fractional" else []),
                    *([
                        _kv_row("Lot Size", fl.get("lot", "—")),
                    ] if model == "fixed_lot" else []),
                    *([
                        _kv_row("Risk %",          f"{va.get('risk_pct', '—')}%"),
                        _kv_row("ATR Ref Period",   va.get("atr_reference_period", "—")),
                        _kv_row("ATR Scale",        va.get("atr_size_scale", "—")),
                    ] if model == "volatility_adjusted" else []),
                    *([
                        _kv_row("Kelly Enabled",   "Yes" if kelly.get("enabled") else "No"),
                        _kv_row("Kelly Fraction",  kelly.get("kelly_fraction_cap", "—")),
                        _kv_row("Max Risk %",       f"{kelly.get('max_risk_pct', '—')}%"),
                        _kv_row("Min Trades",       kelly.get("min_trades_required", "—")),
                        _kv_row("Lookback",         kelly.get("lookback_trades", "—")),
                    ] if model == "fractional_kelly" else []),
                ])),
            ], width=4),

            # ── Column 2: Constraints ─────────────────────────── #
            dbc.Col([
                _section("Risk Constraints", html.Div([
                    _kv_row("Max Positions",        constraints.get("max_positions", "—")),
                    _kv_row("Max Open Risk",         f"{constraints.get('max_open_risk_pct', '—')}%"),
                    _kv_row("Min Stop",              f"{constraints.get('min_stop_pips', '—')} pips"),
                    _kv_row("Max Stop",              f"{constraints.get('max_stop_pips', '—')} pips"),
                    html.Div(style={"height": "12px"}),
                    _constraint_bar("Daily Loss Limit",    max_dl,  10, _AMBER),
                    _constraint_bar("Max Open Risk",       max_r,   5,  _BLUE),
                    _constraint_bar("Drawdown Halt",       max_dd,  30, _RED),
                ])),
            ], width=4),

            # ── Column 3: All models reference ───────────────── #
            dbc.Col([
                _section("All Models", html.Div([
                    html.Div("Fixed Lot", style={"fontSize": "11px", "color": _BLUE, "fontWeight": "700", "marginBottom": "4px"}),
                    _kv_row("Lot Size", fl.get("lot", "—")),
                    html.Hr(style={"borderColor": _BORDER, "margin": "8px 0"}),

                    html.Div("Fixed Fractional", style={"fontSize": "11px", "color": _TEAL, "fontWeight": "700", "marginBottom": "4px"}),
                    _kv_row("Risk %", f"{ff.get('risk_pct', '—')}%"),
                    html.Hr(style={"borderColor": _BORDER, "margin": "8px 0"}),

                    html.Div("Volatility Adjusted", style={"fontSize": "11px", "color": _AMBER, "fontWeight": "700", "marginBottom": "4px"}),
                    _kv_row("Risk %",        f"{va.get('risk_pct', '—')}%"),
                    _kv_row("ATR Period",    va.get("atr_reference_period", "—")),
                    html.Hr(style={"borderColor": _BORDER, "margin": "8px 0"}),

                    html.Div("Fractional Kelly", style={"fontSize": "11px", "color": _RED, "fontWeight": "700", "marginBottom": "4px"}),
                    _kv_row("Enabled",       "Yes" if kelly.get("enabled") else "No"),
                    _kv_row("Kelly Fraction", kelly.get("kelly_fraction_cap", "—")),
                    _kv_row("Max Risk %",    f"{kelly.get('max_risk_pct', '—')}%"),
                ])),
            ], width=4),
        ], className="g-3"),

    ], style={"padding": "24px"})
