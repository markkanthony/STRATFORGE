"""
ui/pages/home.py — StratForge home page: project list + global analytics.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc

from ui.data.projects import list_projects
from ui.data.loader import load_history

# ------------------------------------------------------------------ #
# Design tokens                                                        #
# ------------------------------------------------------------------ #

_BG      = "#0b0e17"
_SURFACE = "#111827"
_CARD    = "#161d2f"
_BORDER  = "#1e2d47"
_BLUE    = "#3b82f6"
_TEAL    = "#14b8a6"
_RED     = "#ef4444"
_AMBER   = "#f59e0b"
_TEXT    = "#e2e8f0"
_MUTED   = "#64748b"
_DIM     = "#334155"


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _fmt_pct(val, sign=True) -> str:
    if val is None:
        return "—"
    s = f"+{val*100:.1f}%" if (val >= 0 and sign) else f"{val*100:.1f}%"
    return s


def _fmt_num(val, precision=2) -> str:
    if val is None:
        return "—"
    return f"{val:.{precision}f}"


def _color_sharpe(v) -> str:
    if v is None:
        return _MUTED
    return _TEAL if v > 0 else _RED


def _color_pct(v) -> str:
    if v is None:
        return _MUTED
    return _TEAL if v >= 0 else _RED


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


def _kpi(label: str, value: str, color: str = _TEXT) -> html.Div:
    return html.Div([
        html.Div(label, style={
            "fontSize": "10px",
            "letterSpacing": "0.08em",
            "textTransform": "uppercase",
            "color": _MUTED,
            "marginBottom": "5px",
        }),
        html.Div(value, style={
            "fontSize": "22px",
            "fontWeight": "700",
            "fontFamily": "'Courier New', monospace",
            "color": color,
            "lineHeight": 1,
        }),
    ])


# ------------------------------------------------------------------ #
# Global stats bar                                                      #
# ------------------------------------------------------------------ #

def _build_stats_bar(history: list) -> html.Div:
    if not history:
        return html.Div()

    n         = len(history)
    best_s    = max((h.get("val_sharpe") or 0) for h in history)
    best_r    = max((h.get("val_return") or 0) for h in history)
    worst_dd  = min((h.get("val_drawdown") or 0) for h in history)

    divider = html.Div(style={
        "width": "1px", "background": _BORDER,
        "height": "36px", "alignSelf": "center", "margin": "0 28px",
    })

    return html.Div([
        _kpi("Total Runs",    str(n)),
        divider,
        _kpi("Best Sharpe",   _fmt_num(best_s),        _color_sharpe(best_s)),
        divider,
        _kpi("Best Return",   _fmt_pct(best_r),         _color_pct(best_r)),
        divider,
        _kpi("Worst Drawdown", _fmt_pct(worst_dd, sign=False), _RED if worst_dd < -0.05 else _MUTED),
    ], style={
        "display": "flex",
        "alignItems": "center",
        "padding": "18px 32px",
        "background": _SURFACE,
        "borderBottom": f"1px solid {_BORDER}",
    })


# ------------------------------------------------------------------ #
# Project card                                                         #
# ------------------------------------------------------------------ #

def _build_project_card(p: dict) -> dbc.Col:
    sharpe    = p.get("best_sharpe")
    ret       = p.get("last_val_return")
    dd        = p.get("last_val_drawdown")
    trades    = p.get("last_val_trades")
    mode      = p.get("mode", "hybrid")
    run_count = p.get("run_count", 0)
    last_run  = p.get("last_run") or "—"

    sharpe_color = _color_sharpe(sharpe)
    ret_color    = _color_pct(ret)
    dd_color     = _RED if (dd or 0) < -0.10 else (_AMBER if (dd or 0) < -0.05 else _MUTED)

    mode_color = {"indicator": _BLUE, "pattern": _AMBER, "hybrid": _TEAL}.get(mode, _BLUE)

    # Left accent bar color = sharpe quality
    accent = sharpe_color if sharpe is not None else _BORDER

    card = html.Div([
        # Header: symbol + mode badge
        html.Div([
            html.Div([
                html.Span("●", style={"color": _TEAL, "fontSize": "9px", "marginRight": "7px", "verticalAlign": "middle"}),
                html.Span(
                    f"{p['symbol']} · {p['timeframe']}",
                    style={"fontWeight": "700", "fontSize": "14px", "color": _TEXT, "letterSpacing": "0.03em"},
                ),
            ]),
            _badge(mode, mode_color),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "4px"}),

        html.Div(p["name"], style={"fontSize": "12px", "color": _MUTED, "marginBottom": "22px"}),

        # Metric trio
        html.Div([
            _kpi("Sharpe",  _fmt_num(sharpe),          sharpe_color),
            html.Div(style={"width": "1px", "background": _BORDER, "height": "36px", "alignSelf": "center"}),
            _kpi("Return",  _fmt_pct(ret),              ret_color),
            html.Div(style={"width": "1px", "background": _BORDER, "height": "36px", "alignSelf": "center"}),
            _kpi("Max DD",  _fmt_pct(dd, sign=False),  dd_color),
        ], style={"display": "flex", "gap": "20px", "alignItems": "center", "marginBottom": "22px"}),

        # Footer: runs + last run + open link
        html.Div([
            html.Div([
                html.Span(f"{run_count} run{'s' if run_count != 1 else ''}", style={"fontSize": "11px", "color": _MUTED}),
                html.Span(" · ", style={"color": _DIM}),
                html.Span(f"Last: {last_run}", style={"fontSize": "11px", "color": _MUTED}),
                html.Span(f" · {trades} trades" if trades else "", style={"fontSize": "11px", "color": _MUTED}),
            ]),
            dcc.Link(
                "Open →",
                href="/project",
                style={
                    "fontSize": "12px",
                    "fontWeight": "700",
                    "color": _BLUE,
                    "textDecoration": "none",
                    "padding": "5px 12px",
                    "borderRadius": "5px",
                    "border": f"1px solid {_BLUE}44",
                    "background": f"{_BLUE}0d",
                    "transition": "background 0.15s",
                },
            ),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"}),

    ], style={
        "background": _CARD,
        "border": f"1px solid {_BORDER}",
        "borderLeft": f"3px solid {accent}",
        "borderRadius": "10px",
        "padding": "22px 24px",
        "height": "100%",
        "transition": "border-color 0.2s",
    })

    return dbc.Col(card, md=6, lg=4, style={"marginBottom": "16px"})


# ------------------------------------------------------------------ #
# Page builder                                                         #
# ------------------------------------------------------------------ #

def build_home_layout() -> html.Div:
    """Return the complete home page content (always in DOM, shown via CSS)."""
    history  = load_history()
    projects = list_projects()

    return html.Div([
        # ── Top bar ────────────────────────────────────────────── #
        html.Div([
            html.Div([
                html.Span("⚡", style={"color": _BLUE, "fontSize": "18px", "marginRight": "8px"}),
                html.Span("StratForge", style={
                    "fontWeight": "900",
                    "fontSize": "17px",
                    "letterSpacing": "0.06em",
                    "color": _TEXT,
                }),
            ], style={"display": "flex", "alignItems": "center"}),

            html.Div([
                html.Span("Backtesting Platform", style={"fontSize": "11px", "color": _MUTED, "marginRight": "16px"}),
                html.Button(
                    "+ New Project",
                    id="btn-create-project",
                    style={
                        "fontSize": "12px",
                        "fontWeight": "700",
                        "color": _BLUE,
                        "background": f"{_BLUE}0d",
                        "border": f"1px solid {_BLUE}44",
                        "borderRadius": "6px",
                        "padding": "6px 14px",
                        "cursor": "pointer",
                    },
                ),
            ], style={"display": "flex", "alignItems": "center"}),
        ], style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "14px 32px",
            "background": "#0b0e17",
            "borderBottom": f"1px solid {_BORDER}",
        }),

        # ── Create project modal ───────────────────────────────── #
        dbc.Modal([
            dbc.ModalHeader(
                dbc.ModalTitle("New Project", style={"fontSize": "15px", "fontWeight": "700", "color": _TEXT}),
                style={"background": "#1c253d", "borderBottom": f"1px solid {_BORDER}"},
                close_button=True,
            ),
            dbc.ModalBody([
                html.P(
                    "Projects are defined by a config.yaml file. "
                    "Create a new config.yaml in the project root to add a project.",
                    style={"fontSize": "13px", "color": _MUTED, "marginBottom": "20px"},
                ),
                html.Div([
                    html.Div("Symbol", style={"fontSize": "11px", "color": _MUTED, "marginBottom": "5px"}),
                    dbc.Input(id="new-project-symbol", placeholder="e.g. EURUSD", type="text",
                              style={"background": "#131722", "border": f"1px solid {_BORDER}",
                                     "color": _TEXT, "fontSize": "13px"}),
                ], style={"marginBottom": "14px"}),
                html.Div([
                    html.Div("Timeframe", style={"fontSize": "11px", "color": _MUTED, "marginBottom": "5px"}),
                    dbc.Select(
                        id="new-project-timeframe",
                        options=[
                            {"label": "M15", "value": "M15"},
                            {"label": "M30", "value": "M30"},
                            {"label": "H1",  "value": "H1"},
                            {"label": "H4",  "value": "H4"},
                            {"label": "D1",  "value": "D1"},
                        ],
                        value="H1",
                        style={"background": "#131722", "border": f"1px solid {_BORDER}",
                               "color": _TEXT, "fontSize": "13px"},
                    ),
                ], style={"marginBottom": "14px"}),
                html.Div([
                    html.Div("Strategy Mode", style={"fontSize": "11px", "color": _MUTED, "marginBottom": "5px"}),
                    dbc.RadioItems(
                        id="new-project-mode",
                        options=[
                            {"label": "Hybrid",    "value": "hybrid"},
                            {"label": "Indicator", "value": "indicator"},
                            {"label": "Pattern",   "value": "pattern"},
                        ],
                        value="hybrid",
                        inline=True,
                        labelStyle={"fontSize": "13px", "marginRight": "16px", "cursor": "pointer"},
                    ),
                ], style={"marginBottom": "8px"}),
                html.Div(id="new-project-msg", style={"fontSize": "12px", "marginTop": "10px"}),
            ], style={"background": "#111827"}),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="btn-create-project-cancel", color="secondary", outline=True,
                           size="sm", style={"marginRight": "8px"}),
                dbc.Button("Create Project", id="btn-create-project-confirm", color="primary",
                           size="sm", style={"fontWeight": "700"}),
            ], style={"background": "#1c253d", "borderTop": f"1px solid {_BORDER}"}),
        ], id="modal-create-project", is_open=False,
           style={"fontFamily": "'Inter', 'Segoe UI', sans-serif"},
           backdrop=True),

        # ── Global stats bar ───────────────────────────────────── #
        _build_stats_bar(history),

        # ── Projects grid ──────────────────────────────────────── #
        html.Div([
            html.Div([
                html.H5("Projects", style={
                    "color": _TEXT,
                    "fontWeight": "700",
                    "fontSize": "15px",
                    "margin": 0,
                }),
                html.Span(
                    f"{len(projects)} project{'s' if len(projects) != 1 else ''}",
                    style={"fontSize": "12px", "color": _MUTED},
                ),
            ], style={"display": "flex", "alignItems": "center", "gap": "12px", "marginBottom": "20px"}),

            (
                dbc.Row([_build_project_card(p) for p in projects], className="g-3")
                if projects else
                html.Div("No projects found.", style={"color": _MUTED, "padding": "40px 0", "textAlign": "center"})
            ),
        ], style={"padding": "28px 32px"}),

    ], style={
        "background": _BG,
        "minHeight": "100vh",
        "color": _TEXT,
        "fontFamily": "'Inter', 'Segoe UI', sans-serif",
    })
