"""
ui/components/run_selector.py

Sidebar run list + window toggle + "Run New Backtest" button.
Also provides build_run_list_items() for dynamic refresh after a new run.
"""

import dash_bootstrap_components as dbc
from dash import html, dcc

from ui.data.loader import load_history, get_latest_run_number


def _run_card(h: dict, is_active: bool) -> dbc.ListGroupItem:
    run_num = h.get("run", 0)
    ts = h.get("timestamp", "")[:10]
    val_sharpe = h.get("val_sharpe")
    sharpe_str = f"{val_sharpe:.2f}" if val_sharpe is not None else "—"
    sharpe_color = "#26a69a" if (val_sharpe or 0) > 0 else "#ef5350"

    return dbc.ListGroupItem(
        [
            html.Div(
                [
                    html.Span(f"Run #{run_num}", style={"fontWeight": "700", "fontSize": "13px"}),
                    html.Span(
                        sharpe_str,
                        style={"color": sharpe_color, "fontSize": "12px", "float": "right", "fontWeight": "600"},
                    ),
                ],
            ),
            html.Div(ts, style={"color": "#758696", "fontSize": "11px"}),
        ],
        id={"type": "run-list-item", "index": run_num},
        action=True,
        active=is_active,
        style={
            "backgroundColor": "#1e222d" if is_active else "#161a25",
            "borderLeft": f"3px solid #2962ff" if is_active else "3px solid transparent",
            "cursor": "pointer",
            "padding": "8px 12px",
            "marginBottom": "2px",
            "borderRadius": "4px",
            "transition": "background 0.15s",
        },
    )


def build_run_list_items(active_run: int = None) -> list:
    """Build the list of run cards from history.jsonl."""
    history = load_history()
    if not history:
        return [
            html.Div(
                "No runs yet",
                style={"color": "#758696", "fontSize": "12px", "padding": "8px"},
            )
        ]
    return [_run_card(h, h.get("run") == active_run) for h in history]


def build_sidebar(static: bool = False) -> html.Div:
    """Build the full sidebar component.

    static=True: position:relative for embedding inside a flex container.
    static=False (default): position:fixed for the standalone layout.
    """
    latest = get_latest_run_number()

    _pos = (
        {"position": "relative", "top": "auto", "left": "auto",
         "height": "100%", "zIndex": "auto", "minHeight": "100vh"}
        if static else
        {"position": "fixed", "top": 0, "left": 0, "height": "100vh", "zIndex": 100}
    )

    return html.Div(
        [
            # Logo / title
            html.Div(
                [
                    html.Span("⚡", style={"marginRight": "6px"}),
                    html.Span("StratForge", style={"fontWeight": "900", "letterSpacing": "0.06em"}),
                ],
                style={
                    "fontSize": "17px",
                    "color": "#d1d4dc",
                    "padding": "16px 12px 12px",
                    "borderBottom": "1px solid #2a2e39",
                    "marginBottom": "8px",
                },
            ),

            # Run list header
            html.Div(
                "RUNS",
                style={
                    "fontSize": "10px",
                    "fontWeight": "700",
                    "letterSpacing": "0.12em",
                    "color": "#758696",
                    "padding": "4px 12px 4px",
                },
            ),

            # Scrollable run list
            html.Div(
                dbc.ListGroup(
                    id="sidebar-run-list",
                    children=build_run_list_items(latest),
                    flush=True,
                    style={"background": "transparent"},
                ),
                style={
                    "maxHeight": "340px",
                    "overflowY": "auto",
                    "padding": "0 8px",
                    "marginBottom": "12px",
                },
            ),

            html.Hr(style={"borderColor": "#2a2e39", "margin": "4px 12px"}),

            # Window toggle
            html.Div(
                [
                    html.Div(
                        "WINDOW",
                        style={
                            "fontSize": "10px",
                            "fontWeight": "700",
                            "letterSpacing": "0.12em",
                            "color": "#758696",
                            "marginBottom": "6px",
                        },
                    ),
                    dbc.RadioItems(
                        id="window-toggle",
                        options=[
                            {"label": "Validation", "value": "validation"},
                            {"label": "Train",      "value": "train"},
                        ],
                        value="validation",
                        inline=False,
                        inputStyle={"marginRight": "6px"},
                        labelStyle={"fontSize": "13px", "cursor": "pointer"},
                    ),
                ],
                style={"padding": "8px 12px"},
            ),

            html.Hr(style={"borderColor": "#2a2e39", "margin": "4px 12px"}),

            # Run button + status
            html.Div(
                [
                    dbc.Button(
                        "▶  Run New Backtest",
                        id="btn-run-backtest",
                        color="primary",
                        size="sm",
                        style={"width": "100%", "fontWeight": "700", "marginBottom": "6px"},
                    ),
                    html.Div(
                        "● Ready",
                        id="backtest-status-text",
                        style={"fontSize": "11px", "color": "#758696", "textAlign": "center"},
                    ),
                    # Polling interval (disabled until backtest starts)
                    dcc.Interval(
                        id="poll-interval",
                        interval=2000,
                        disabled=True,
                    ),
                ],
                style={"padding": "8px 12px"},
            ),
        ],
        style={
            "width": "240px",
            "minWidth": "240px",
            "background": "#0e1117",
            "borderRight": "1px solid #2a2e39",
            "overflowY": "auto",
            **_pos,
        },
    )
