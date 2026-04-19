"""
ui/layout.py

Top-level Dash app layout.
Sidebar (fixed left) + main content area (tabs + metrics panel).
"""

import dash_bootstrap_components as dbc
from dash import html, dcc

from ui.components.run_selector import build_sidebar
from ui.data.loader import get_latest_run_number


def build_layout() -> html.Div:
    """Build and return the top-level app layout."""
    latest_run = get_latest_run_number()

    return html.Div(
        [
            # ---- Shared stores ------------------------------------ #
            dcc.Store(id="store-selected-run",        data=latest_run),
            dcc.Store(id="store-selected-window",     data="validation"),
            dcc.Store(id="store-run-data",            data=None),
            dcc.Store(id="store-highlighted-trade-idx", data=None),

            # ---- Sidebar (fixed left) ----------------------------- #
            build_sidebar(),

            # ---- Main content area (offset by sidebar width) ------ #
            html.Div(
                [
                    # Tabs navigation
                    dbc.Tabs(
                        [
                            dbc.Tab(label="Dashboard", tab_id="tab-dashboard",
                                    label_style={"fontSize": "13px", "padding": "10px 16px"},
                                    active_label_style={"fontWeight": "700", "color": "#2962ff"}),
                            dbc.Tab(label="Chart",     tab_id="tab-chart",
                                    label_style={"fontSize": "13px", "padding": "10px 16px"},
                                    active_label_style={"fontWeight": "700", "color": "#2962ff"}),
                            dbc.Tab(label="Journal",   tab_id="tab-journal",
                                    label_style={"fontSize": "13px", "padding": "10px 16px"},
                                    active_label_style={"fontWeight": "700", "color": "#2962ff"}),
                        ],
                        id="main-tabs",
                        active_tab="tab-dashboard",
                        style={
                            "backgroundColor": "#0e1117",
                            "borderBottom": "2px solid #2a2e39",
                            "paddingLeft": "8px",
                        },
                    ),

                    # Dynamic tab content
                    html.Div(id="tab-content", style={"minHeight": "600px"}),

                    # Metrics panel — always visible below tab content
                    html.Div(id="metrics-panel-container"),
                ],
                style={
                    "marginLeft": "240px",    # offset by sidebar width
                    "minHeight": "100vh",
                    "backgroundColor": "#131722",
                    "color": "#d1d4dc",
                },
            ),
        ],
        style={
            "margin": 0,
            "padding": 0,
            "fontFamily": "'Inter', 'Segoe UI', sans-serif",
            "backgroundColor": "#131722",
        },
    )
