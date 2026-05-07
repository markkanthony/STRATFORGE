"""
ui/pages/strategy_view.py — 3-mode strategy workshop.

Mode 1: Copy-Paste  — generate prompt, paste AI output, apply & run
Mode 2: Agent       — call Claude API directly, preview, apply & run
Mode 3: Auto-Loop   — fully automated ai_loop.py iteration
"""

from dash import html, dcc
import dash_bootstrap_components as dbc

from ui.data.projects import load_config, load_strategy_history

_CARD   = "#161d2f"
_CARD2  = "#0f1624"
_BORDER = "#1e2d47"
_BLUE   = "#3b82f6"
_TEAL   = "#14b8a6"
_RED    = "#ef4444"
_AMBER  = "#f59e0b"
_TEXT   = "#e2e8f0"
_MUTED  = "#64748b"
_GREEN  = "#22c55e"


# ── Shared style helpers ──────────────────────────────────────────── #

def _section(title: str, content, extra_style: dict = None) -> html.Div:
    style = {
        "background": _CARD,
        "border": f"1px solid {_BORDER}",
        "borderRadius": "8px",
        "padding": "18px 20px",
        **(extra_style or {}),
    }
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
    ], style=style)


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


def _btn(label: str, btn_id: str, color: str = _BLUE, disabled: bool = False) -> html.Button:
    return html.Button(label, id=btn_id, disabled=disabled, style={
        "background": f"{color}1a",
        "color": color,
        "border": f"1px solid {color}55",
        "borderRadius": "6px",
        "padding": "7px 16px",
        "fontSize": "13px",
        "fontWeight": "600",
        "cursor": "pointer" if not disabled else "not-allowed",
        "opacity": "0.5" if disabled else "1",
    })


def _mode_btn(label: str, btn_id: str, active: bool = False) -> html.Button:
    color = _BLUE if active else _MUTED
    return html.Button(label, id=btn_id, style={
        "background": f"{color}15" if active else "transparent",
        "color": color,
        "border": f"1px solid {color}{'55' if active else '22'}",
        "borderRadius": "6px",
        "padding": "7px 18px",
        "fontSize": "12px",
        "fontWeight": "700",
        "cursor": "pointer",
        "letterSpacing": "0.03em",
    })


def _status_span(text: str, span_id: str, color: str = _MUTED) -> html.Span:
    return html.Span(text, id=span_id, style={
        "fontSize": "12px",
        "color": color,
        "marginLeft": "12px",
    })


# ── History table ─────────────────────────────────────────────────── #

def _build_history_table(history: list) -> html.Div:
    if not history:
        return html.Div("No runs yet.", style={"color": _MUTED, "fontSize": "13px"})

    header = html.Tr([
        html.Th(col, style={"color": _MUTED, "fontSize": "10px", "fontWeight": "700",
                            "letterSpacing": "0.08em", "textTransform": "uppercase",
                            "padding": "6px 12px", "borderBottom": f"1px solid {_BORDER}"})
        for col in ["Run", "Val Sharpe", "Drawdown", "Trades", "Type", "Δ Sharpe"]
    ])

    rows = []
    for h in history:
        sharpe = h.get("val_sharpe")
        dd = h.get("val_drawdown")
        delta = h.get("delta_sharpe")
        ct = h.get("change_type") or "—"

        sharpe_str = f"{sharpe:.3f}" if sharpe is not None else "—"
        dd_str = f"{dd * 100:.1f}%" if dd is not None else "—"
        trades_str = str(h.get("val_trades") or "—")

        if delta is None:
            delta_cell = html.Td("baseline", style={"color": _MUTED, "fontSize": "11px",
                                                     "padding": "6px 12px"})
        else:
            sign = "+" if delta >= 0 else ""
            delta_color = _GREEN if delta > 0 else (_RED if delta < 0 else _MUTED)
            delta_cell = html.Td(f"{sign}{delta:.3f}", style={"color": delta_color,
                                                               "fontWeight": "600",
                                                               "fontSize": "12px",
                                                               "fontFamily": "monospace",
                                                               "padding": "6px 12px"})

        type_color = {"config": _TEAL, "code": _AMBER, "both": _BLUE}.get(ct, _MUTED)

        row = html.Tr([
            html.Td(str(h.get("run") or "—"),
                    style={"color": _MUTED, "fontSize": "12px", "padding": "6px 12px",
                           "fontFamily": "monospace"}),
            html.Td(sharpe_str,
                    style={"color": _TEXT, "fontSize": "13px", "fontWeight": "600",
                           "fontFamily": "monospace", "padding": "6px 12px"}),
            html.Td(dd_str,
                    style={"color": _AMBER if dd and dd < -0.1 else _TEXT,
                           "fontSize": "12px", "fontFamily": "monospace", "padding": "6px 12px"}),
            html.Td(trades_str,
                    style={"color": _MUTED, "fontSize": "12px", "padding": "6px 12px"}),
            html.Td(_badge(ct, type_color),
                    style={"padding": "6px 12px"}),
            delta_cell,
        ], style={"borderBottom": f"1px solid {_BORDER}22"})
        rows.append(row)

    return html.Table([
        html.Thead(header),
        html.Tbody(rows),
    ], style={"width": "100%", "borderCollapse": "collapse"})


# ── Mode panels ───────────────────────────────────────────────────── #

def _build_mode1_panel() -> html.Div:
    return html.Div([
        dbc.Row([
            dbc.Col([
                _section("Prompt — copy and paste into any AI chat", html.Div([
                    html.Div([
                        dcc.Clipboard(
                            id="strategy-copy-btn",
                            target_id="strategy-prompt-pre",
                            title="Copy to clipboard",
                            style={"fontSize": "12px", "color": _BLUE, "cursor": "pointer",
                                   "float": "right"},
                        ),
                    ]),
                    html.Pre(
                        id="strategy-prompt-pre",
                        children="Loading prompt…",
                        style={
                            "fontSize": "11px",
                            "color": _MUTED,
                            "background": _CARD2,
                            "borderRadius": "6px",
                            "padding": "12px",
                            "maxHeight": "220px",
                            "overflowY": "auto",
                            "whiteSpace": "pre-wrap",
                            "wordBreak": "break-word",
                            "margin": 0,
                            "clear": "both",
                        },
                    ),
                ])),
            ], width=6),

            dbc.Col([
                _section("AI Output — paste response here", html.Div([
                    dcc.Textarea(
                        id="strategy-paste-area",
                        placeholder=(
                            "Paste AI output here.\n\n"
                            "Expected format:\n"
                            "  change_type: config\n"
                            "  strategy:\n"
                            "    indicators:\n"
                            "      fast_ema: 8\n"
                            "  ...\n\n"
                            "or:\n"
                            "  change_type: code\n"
                            "  def generate_signals(df, config):\n"
                            "      ..."
                        ),
                        style={
                            "width": "100%",
                            "height": "180px",
                            "background": _CARD2,
                            "color": _TEXT,
                            "border": f"1px solid {_BORDER}",
                            "borderRadius": "6px",
                            "padding": "10px",
                            "fontSize": "12px",
                            "fontFamily": "monospace",
                            "resize": "vertical",
                        },
                    ),
                    html.Div([
                        _btn("Apply & Run ▶", "strategy-apply-btn-1"),
                        _status_span("● Ready", "strategy-apply-status-1"),
                    ], style={"marginTop": "10px", "display": "flex", "alignItems": "center"}),
                    html.Div(id="strategy-apply-errors-1", style={"marginTop": "8px"}),
                ])),
            ], width=6),
        ], className="g-3"),
    ])


def _build_mode2_panel() -> html.Div:
    return html.Div([
        _section("Agent — Claude generates and applies changes automatically", html.Div([
            html.Div([
                _btn("Generate with Claude ▶", "strategy-generate-btn"),
                _status_span("", "strategy-generate-status"),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "16px"}),

            html.Div(id="strategy-generate-preview"),

            html.Div([
                _btn("Apply & Run ▶", "strategy-apply-btn-2", disabled=True),
                _status_span("", "strategy-apply-status-2"),
            ], style={"marginTop": "12px", "display": "flex", "alignItems": "center"}),
            html.Div(id="strategy-apply-errors-2", style={"marginTop": "8px"}),
        ])),
    ])


def _build_mode3_panel() -> html.Div:
    return html.Div([
        _section("Auto-Loop — runs ai_loop.py autonomously until convergence or max iterations", html.Div([
            html.Div([
                html.Span("Max iterations:", style={"color": _MUTED, "fontSize": "13px",
                                                    "marginRight": "10px"}),
                dbc.Input(
                    id="strategy-loop-max-iter",
                    value=20,
                    type="number",
                    min=1,
                    max=100,
                    style={
                        "width": "80px",
                        "background": _CARD2,
                        "color": _TEXT,
                        "border": f"1px solid {_BORDER}",
                        "borderRadius": "6px",
                        "padding": "4px 8px",
                        "fontSize": "13px",
                    },
                ),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "16px"}),

            html.Div([
                _btn("Start Auto-Loop ▶", "strategy-loop-start-btn", color=_TEAL),
                html.Span(" ", style={"width": "8px", "display": "inline-block"}),
                _btn("Stop ■", "strategy-loop-stop-btn", color=_RED, disabled=True),
            ], style={"display": "flex", "gap": "8px", "marginBottom": "16px"}),

            html.Div(id="strategy-loop-status",
                     children="● Ready",
                     style={"color": _MUTED, "fontSize": "13px", "fontFamily": "monospace"}),

            dcc.Interval(id="strategy-loop-interval", interval=2000, disabled=True),
        ])),
    ])


# ── Main layout ───────────────────────────────────────────────────── #

def build_strategy_content() -> html.Div:
    history = load_strategy_history()

    return html.Div([
        # Header
        html.Div([
            html.H5("Strategy Workshop", style={
                "color": _TEXT, "fontWeight": "700", "fontSize": "15px", "margin": 0,
            }),
            html.Span("3 modes · token-efficient prompts · run history", style={
                "fontSize": "12px", "color": _MUTED,
            }),
        ], style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "marginBottom": "20px",
            "paddingBottom": "14px",
            "borderBottom": f"1px solid {_BORDER}",
        }),

        # Run history
        _section("Run History", html.Div(
            id="strategy-history-table",
            children=_build_history_table(history),
        ), extra_style={"marginBottom": "20px"}),

        # Mode selector
        html.Div([
            _mode_btn("Mode 1 · Copy-Paste", "strategy-mode-btn-1", active=True),
            _mode_btn("Mode 2 · Agent",      "strategy-mode-btn-2"),
            _mode_btn("Mode 3 · Auto-Loop",  "strategy-mode-btn-3"),
        ], style={"display": "flex", "gap": "8px", "marginBottom": "20px"}),

        # Mode panels (toggled by callbacks)
        html.Div(id="strategy-panel-1", children=_build_mode1_panel()),
        html.Div(id="strategy-panel-2", children=_build_mode2_panel(),
                 style={"display": "none"}),
        html.Div(id="strategy-panel-3", children=_build_mode3_panel(),
                 style={"display": "none"}),

    ], style={"padding": "24px"})
