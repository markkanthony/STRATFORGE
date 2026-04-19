"""
ui/pages/project.py — Project shell: left nav + four section panels.

All section panels (overview, strategy, risk, analysis) are always in the DOM.
Visibility is toggled via display:none/block by nav_callbacks so that the
legacy component IDs inside section-analysis survive across section switches.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc

from ui.components.run_selector import build_sidebar
from ui.pages.overview      import build_overview_content
from ui.pages.strategy_view import build_strategy_content
from ui.pages.risk_view     import build_risk_content
from ui.pages.dashboard     import build_dashboard_layout
from ui.components.metrics_panel import build_metrics_panel
from ui.data.projects import list_projects

_BG      = "#0b0e17"
_SURFACE = "#111827"
_NAV_BG  = "#0e1117"
_BORDER  = "#1e2d47"
_BLUE    = "#3b82f6"
_TEAL    = "#14b8a6"
_TEXT    = "#e2e8f0"
_MUTED   = "#64748b"
_ACTIVE  = "#1c253d"

_NAV_W   = "160px"   # left nav width
_RUN_W   = "240px"   # run selector width (inside analysis section)


# ------------------------------------------------------------------ #
# Nav button helpers                                                   #
# ------------------------------------------------------------------ #

def _nav_btn_style(active: bool) -> dict:
    return {
        "display": "block",
        "width": "100%",
        "padding": "10px 16px",
        "background": _ACTIVE if active else "transparent",
        "border": "none",
        "borderLeft": f"3px solid {_BLUE}" if active else "3px solid transparent",
        "color": _TEXT if active else _MUTED,
        "fontWeight": "600" if active else "400",
        "fontSize": "13px",
        "textAlign": "left",
        "cursor": "pointer",
        "transition": "background 0.15s, color 0.15s",
        "letterSpacing": "0.01em",
    }


def _nav_sep() -> html.Hr:
    return html.Hr(style={"borderColor": _BORDER, "margin": "8px 12px"})


# ------------------------------------------------------------------ #
# Project page builder                                                 #
# ------------------------------------------------------------------ #

def build_project_page(run_data: dict = None, window: str = "validation") -> html.Div:
    """
    Build the complete project page.

    run_data / window are used to pre-populate section content on first render.
    nav_callbacks updates section visibility and overview content reactively.
    """
    projects = list_projects()
    p        = projects[0] if projects else {}
    symbol   = p.get("symbol", "EURUSD")
    tf       = p.get("timeframe", "H1")
    mode     = p.get("mode", "hybrid")

    mode_colors = {"indicator": _BLUE, "pattern": "#f59e0b", "hybrid": _TEAL}
    mc = mode_colors.get(mode, _BLUE)

    return html.Div([

        # ── Fixed left navigation ──────────────────────────── #
        html.Div([
            # Logo → back to home
            dcc.Link(
                html.Div([
                    html.Span("⚡", style={"color": _BLUE, "fontSize": "16px", "marginRight": "6px"}),
                    html.Span("StratForge", style={
                        "fontWeight": "900",
                        "fontSize": "14px",
                        "letterSpacing": "0.06em",
                        "color": _TEXT,
                    }),
                ], style={"display": "flex", "alignItems": "center", "padding": "16px 14px 12px"}),
                href="/",
                style={"textDecoration": "none", "display": "block"},
            ),

            html.Div(style={"borderBottom": f"1px solid {_BORDER}", "marginBottom": "8px"}),

            # Project meta chip
            html.Div([
                html.Div(f"{symbol} · {tf}", style={"fontSize": "11px", "fontWeight": "700", "color": _TEXT}),
                html.Span(mode, style={
                    "fontSize": "9px",
                    "fontWeight": "700",
                    "textTransform": "uppercase",
                    "letterSpacing": "0.07em",
                    "color": mc,
                    "background": f"{mc}1a",
                    "border": f"1px solid {mc}33",
                    "padding": "2px 6px",
                    "borderRadius": "3px",
                    "marginTop": "3px",
                    "display": "inline-block",
                }),
            ], style={"padding": "6px 14px 10px"}),

            html.Div(style={"borderBottom": f"1px solid {_BORDER}", "marginBottom": "4px"}),

            # Section buttons — styles updated by nav_callbacks.show_section
            html.Button("Overview",  id="nav-btn-overview",  style=_nav_btn_style(True),  n_clicks=0),
            html.Button("Strategy",  id="nav-btn-strategy",  style=_nav_btn_style(False), n_clicks=0),
            html.Button("Risk",      id="nav-btn-risk",      style=_nav_btn_style(False), n_clicks=0),

            _nav_sep(),

            html.Div(
                "Analysis",
                style={"fontSize": "9px", "letterSpacing": "0.1em", "color": _MUTED,
                       "padding": "4px 16px 2px", "textTransform": "uppercase", "fontWeight": "700"},
            ),
            html.Button("Runs",    id="nav-btn-analysis", style=_nav_btn_style(False), n_clicks=0),

        ], style={
            "width": _NAV_W,
            "minWidth": _NAV_W,
            "position": "fixed",
            "top": 0,
            "left": 0,
            "height": "100vh",
            "background": _NAV_BG,
            "borderRight": f"1px solid {_BORDER}",
            "zIndex": 200,
            "display": "flex",
            "flexDirection": "column",
            "overflowY": "auto",
        }),

        # ── Content area (offset by nav width) ────────────── #
        html.Div([

            # ── SECTION: Overview ─────────────────────────── #
            html.Div(
                build_overview_content(run_data, window),
                id="section-overview",
                style={"display": "block"},
            ),

            # ── SECTION: Strategy ─────────────────────────── #
            html.Div(
                build_strategy_content(),
                id="section-strategy",
                style={"display": "none"},
            ),

            # ── SECTION: Risk ─────────────────────────────── #
            html.Div(
                build_risk_content(),
                id="section-risk",
                style={"display": "none"},
            ),

            # ── SECTION: Analysis ─────────────────────────── #
            # Always in DOM (display:none when inactive) so all legacy
            # component IDs (sidebar-run-list, main-tabs, etc.) survive.
            html.Div([
                # Run selector — static mode (position:relative)
                build_sidebar(static=True),

                # Tabs + content + metrics (offset by run selector width)
                html.Div([
                    dbc.Tabs(
                        [
                            dbc.Tab(
                                label="Runs",
                                tab_id="tab-dashboard",
                                label_style={"fontSize": "13px", "padding": "10px 16px"},
                                active_label_style={"fontWeight": "700", "color": _BLUE},
                            ),
                            dbc.Tab(
                                label="Chart",
                                tab_id="tab-chart",
                                label_style={"fontSize": "13px", "padding": "10px 16px"},
                                active_label_style={"fontWeight": "700", "color": _BLUE},
                            ),
                            dbc.Tab(
                                label="Journal",
                                tab_id="tab-journal",
                                label_style={"fontSize": "13px", "padding": "10px 16px"},
                                active_label_style={"fontWeight": "700", "color": _BLUE},
                            ),
                        ],
                        id="main-tabs",
                        active_tab="tab-dashboard",
                        style={
                            "backgroundColor": "#0e1117",
                            "borderBottom": f"2px solid {_BORDER}",
                            "paddingLeft": "8px",
                        },
                    ),

                    # Tab content — pre-built with dashboard on first render
                    html.Div(
                        build_dashboard_layout(),
                        id="tab-content",
                        style={"minHeight": "600px"},
                    ),

                    # Metrics panel — pre-built with current run data
                    html.Div(
                        build_metrics_panel(run_data),
                        id="metrics-panel-container",
                    ),

                ], style={"marginLeft": _RUN_W, "flex": 1}),

            ], id="section-analysis", style={"display": "none", "flexDirection": "row"}),

        ], style={
            "marginLeft": _NAV_W,
            "minHeight": "100vh",
            "backgroundColor": _SURFACE,
            "color": _TEXT,
        }),

    ], style={
        "margin": 0,
        "padding": 0,
        "fontFamily": "'Inter', 'Segoe UI', sans-serif",
        "backgroundColor": _SURFACE,
        "color": _TEXT,
    })
