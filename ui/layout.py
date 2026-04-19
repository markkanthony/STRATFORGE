"""
ui/layout.py

Top-level app layout with URL-based routing.

Two top-level page divs (always in DOM, toggled via display style):
  page-home    — home page: project cards + global analytics
  page-project — project shell: left nav + section panels

All dcc.Store components live at the root level (outside page divs)
so their values survive across page switches.
"""

import dash_bootstrap_components as dbc
from dash import html, dcc

from ui.data.loader import get_latest_run_number
from ui.pages.home    import build_home_layout
from ui.pages.project import build_project_page


def build_layout() -> html.Div:
    """Build and return the full app layout."""
    latest_run = get_latest_run_number()

    return html.Div(
        [
            # ---- URL location tracker ----------------------------- #
            dcc.Location(id="url", refresh=False),

            # ---- Shared stores (root-level, survive page switches) #
            dcc.Store(id="store-selected-run",          data=latest_run),
            dcc.Store(id="store-selected-window",       data="validation"),
            dcc.Store(id="store-run-data",              data=None),
            dcc.Store(id="store-highlighted-trade-idx", data=None),
            dcc.Store(id="store-project-section",       data="overview"),

            # ---- Home page (shown by default) -------------------- #
            html.Div(
                build_home_layout(),
                id="page-home",
                style={"display": "block"},
            ),

            # ---- Project page (hidden by default) ---------------- #
            html.Div(
                build_project_page(),
                id="page-project",
                style={"display": "none"},
            ),
        ],
        style={
            "margin": 0,
            "padding": 0,
            "fontFamily": "'Inter', 'Segoe UI', sans-serif",
            "backgroundColor": "#0b0e17",
        },
    )
