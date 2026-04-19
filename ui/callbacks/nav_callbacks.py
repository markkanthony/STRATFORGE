"""
ui/callbacks/nav_callbacks.py

Three callbacks that drive all navigation:

  A. URL pathname → show/hide page-home / page-project
  B. Nav button clicks → store-project-section
  C. store-project-section → section panel visibility + nav button active styles
  D. store-run-data → refresh overview section content
"""

from dash import Input, Output, State, ctx, no_update

from ui.pages.overview      import build_overview_content
from ui.pages.strategy_view import build_strategy_content
from ui.pages.risk_view     import build_risk_content

_BLUE   = "#3b82f6"
_TEXT   = "#e2e8f0"
_MUTED  = "#64748b"
_ACTIVE = "#1c253d"
_BORDER = "#1e2d47"


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


def register(app):

    # ── A: URL → page visibility ──────────────────────────────── #
    @app.callback(
        Output("page-home",    "style"),
        Output("page-project", "style"),
        Input("url", "pathname"),
    )
    def route_page(pathname):
        if not pathname or pathname == "/":
            return {"display": "block"}, {"display": "none"}
        return {"display": "none"}, {"display": "block"}

    # ── B: Nav button clicks → store-project-section ─────────── #
    @app.callback(
        Output("store-project-section", "data"),
        Input("nav-btn-overview",  "n_clicks"),
        Input("nav-btn-strategy",  "n_clicks"),
        Input("nav-btn-risk",      "n_clicks"),
        Input("nav-btn-analysis",  "n_clicks"),
        prevent_initial_call=True,
    )
    def on_nav_click(*_):
        mapping = {
            "nav-btn-overview":  "overview",
            "nav-btn-strategy":  "strategy",
            "nav-btn-risk":      "risk",
            "nav-btn-analysis":  "analysis",
        }
        return mapping.get(ctx.triggered_id, "overview")

    # ── C: store-project-section → section visibility + nav styles #
    @app.callback(
        Output("section-overview",  "style"),
        Output("section-strategy",  "style"),
        Output("section-risk",      "style"),
        Output("section-analysis",  "style"),
        Output("nav-btn-overview",  "style"),
        Output("nav-btn-strategy",  "style"),
        Output("nav-btn-risk",      "style"),
        Output("nav-btn-analysis",  "style"),
        Input("store-project-section", "data"),
    )
    def show_section(section):
        section = section or "overview"
        names   = ["overview", "strategy", "risk", "analysis"]

        section_styles = []
        nav_styles     = []
        for name in names:
            active = name == section
            section_styles.append(
                {"display": "flex", "flexDirection": "row"} if (active and name == "analysis")
                else ({"display": "block"} if active else {"display": "none"})
            )
            nav_styles.append(_nav_btn_style(active))

        return *section_styles, *nav_styles

    # ── D: store-run-data → refresh overview content ─────────── #
    @app.callback(
        Output("section-overview", "children"),
        Input("store-run-data", "data"),
        State("store-selected-window", "data"),
    )
    def refresh_overview(run_data, window):
        return build_overview_content(run_data, window or "validation")
