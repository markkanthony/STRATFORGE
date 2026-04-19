"""
ui/callbacks/nav_callbacks.py

Callbacks that drive all navigation:

  A. URL pathname → show/hide page-home / page-project
  B. Nav button clicks → store-project-section
  C. store-project-section → section panel visibility + nav button active styles
  D. store-run-data → refresh overview section content
  E. Create Project modal open/close + confirm
"""

from pathlib import Path
import yaml

from dash import Input, Output, State, ctx, no_update

from ui.pages.overview      import build_overview_content
from ui.pages.strategy_view import build_strategy_content
from ui.pages.risk_view     import build_risk_content

_ROOT        = Path(__file__).parent.parent.parent
_CONFIG_PATH = _ROOT / "config.yaml"

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

    # ── E: Create Project modal open/close ────────────────────── #
    @app.callback(
        Output("modal-create-project", "is_open"),
        Input("btn-create-project",        "n_clicks"),
        Input("btn-create-project-cancel", "n_clicks"),
        Input("btn-create-project-confirm","n_clicks"),
        State("modal-create-project",      "is_open"),
        prevent_initial_call=True,
    )
    def toggle_create_modal(n_open, n_cancel, n_confirm, is_open):
        triggered = ctx.triggered_id
        if triggered == "btn-create-project":
            return True
        return False  # cancel or confirm both close

    # ── F: Create Project confirm → write config.yaml ─────────── #
    @app.callback(
        Output("new-project-msg", "children"),
        Output("new-project-msg", "style"),
        Input("btn-create-project-confirm", "n_clicks"),
        State("new-project-symbol",    "value"),
        State("new-project-timeframe", "value"),
        State("new-project-mode",      "value"),
        prevent_initial_call=True,
    )
    def create_project(n_clicks, symbol, timeframe, mode):
        if not symbol or not symbol.strip():
            return "Symbol is required.", {"fontSize": "12px", "color": "#ef4444", "marginTop": "10px"}

        symbol = symbol.strip().upper()

        try:
            # Load existing config to preserve all other settings
            if _CONFIG_PATH.exists():
                with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {}

            config.setdefault("backtest", {})["symbol"]    = symbol
            config.setdefault("backtest", {})["timeframe"] = timeframe or "H1"
            config.setdefault("strategy", {})["mode"]      = mode or "hybrid"

            with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

            return (
                f"✓ Project updated: {symbol} {timeframe} ({mode}). Restart the app to reflect changes.",
                {"fontSize": "12px", "color": "#14b8a6", "marginTop": "10px"},
            )
        except Exception as e:
            return f"Error: {e}", {"fontSize": "12px", "color": "#ef4444", "marginTop": "10px"}
