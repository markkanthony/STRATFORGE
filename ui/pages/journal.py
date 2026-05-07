"""
ui/pages/journal.py

Trade Journal: sortable, filterable DataTable of all trades for the
selected run + window. Clicking a row highlights that trade on the chart.
"""

import dash_bootstrap_components as dbc
from dash import html, dash_table
from dash.dash_table.Format import Format, Scheme, Sign

# ------------------------------------------------------------------ #
# Column definitions                                                   #
# ------------------------------------------------------------------ #

def _col(name, col_id, col_type="numeric", fmt=None):
    c = {"name": name, "id": col_id, "type": col_type}
    if fmt:
        c["format"] = fmt
    return c


_PRICE_FMT = Format(precision=5, scheme=Scheme.fixed)
_PNL_FMT   = Format(precision=2, scheme=Scheme.fixed, sign=Sign.positive)
_R_FMT     = Format(precision=2, scheme=Scheme.fixed, sign=Sign.positive)

JOURNAL_COLUMNS = [
    _col("#",            "trade_idx",      "numeric"),
    _col("Entry Time",   "entry_time_fmt", "text"),
    _col("Exit Time",    "exit_time_fmt",  "text"),
    _col("Side",         "side",           "text"),
    _col("Entry $",      "entry_price",    "numeric", _PRICE_FMT),
    _col("Exit $",       "exit_price",     "numeric", _PRICE_FMT),
    _col("SL $",         "sl_price",       "numeric", _PRICE_FMT),
    _col("TP $",         "tp_price",       "numeric", _PRICE_FMT),
    _col("PnL ($)",      "pnl",            "numeric", _PNL_FMT),
    _col("R-Multiple",   "r_multiple",     "numeric", _R_FMT),
    _col("Exit Reason",  "exit_reason",    "text"),
    _col("Bars Held",    "bars_held",      "numeric"),
    _col("Session",      "entry_session",  "text"),
]

_ID_COLS = {"trade_idx", "entry_time_fmt", "exit_time_fmt"}  # hidden from filter but needed for reference


# ------------------------------------------------------------------ #
# Data prep                                                            #
# ------------------------------------------------------------------ #

def _fmt_time(ts: str) -> str:
    """Format ISO timestamp to readable short form."""
    try:
        import pandas as pd
        t = pd.to_datetime(ts, utc=True)
        return t.strftime("%m-%d %H:%M")
    except Exception:
        return ts[:16] if ts else ""


def trades_to_table_rows(trades: list) -> list:
    """Convert trade dicts to DataTable row dicts."""
    rows = []
    for t in trades:
        rows.append({
            "trade_idx":      t.get("trade_idx", 0),
            "entry_time_fmt": _fmt_time(t.get("entry_time", "")),
            "exit_time_fmt":  _fmt_time(t.get("exit_time", "")),
            "side":           t.get("side", ""),
            "entry_price":    t.get("entry_price"),
            "exit_price":     t.get("exit_price"),
            "sl_price":       t.get("sl_price"),
            "tp_price":       t.get("tp_price"),
            "pnl":            t.get("pnl"),
            "r_multiple":     t.get("r_multiple"),
            "exit_reason":    t.get("exit_reason", ""),
            "bars_held":      t.get("bars_held"),
            "entry_session":  t.get("entry_session", ""),
        })
    return rows


# ------------------------------------------------------------------ #
# Layout                                                               #
# ------------------------------------------------------------------ #

def build_journal_layout() -> html.Div:
    """Return the Journal page layout shell (data populated by callback)."""
    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        "Trade Journal",
                        style={
                            "color": "#d1d4dc",
                            "fontWeight": "700",
                            "fontSize": "14px",
                        },
                    ),
                    html.Span(
                        " — click a row to highlight on chart",
                        style={"color": "#758696", "fontSize": "12px"},
                    ),
                ],
                style={"marginBottom": "10px"},
            ),
            dash_table.DataTable(
                id="trade-journal-table",
                columns=JOURNAL_COLUMNS,
                data=[],
                sort_action="native",
                filter_action="native",
                row_selectable="single",
                selected_rows=[],
                page_size=25,
                style_table={
                    "overflowX": "auto",
                    "borderRadius": "6px",
                    "border": "1px solid #2a2e39",
                },
                style_header={
                    "backgroundColor": "#1e222d",
                    "color": "#d1d4dc",
                    "fontWeight": "700",
                    "fontSize": "11px",
                    "border": "1px solid #2a2e39",
                    "padding": "7px 10px",
                },
                style_cell={
                    "backgroundColor": "#131722",
                    "color": "#d1d4dc",
                    "fontSize": "12px",
                    "border": "1px solid #1e222d",
                    "padding": "6px 10px",
                    "fontFamily": "monospace",
                    "whiteSpace": "normal",
                    "height": "auto",
                    "minWidth": "60px",
                },
                style_data_conditional=[
                    # Win rows — green tint
                    {
                        "if": {"filter_query": "{pnl} > 0"},
                        "backgroundColor": "rgba(38,166,154,0.07)",
                    },
                    {
                        "if": {"filter_query": "{pnl} > 0", "column_id": "pnl"},
                        "color": "#26a69a",
                        "fontWeight": "600",
                    },
                    # Loss rows — red tint
                    {
                        "if": {"filter_query": "{pnl} < 0"},
                        "backgroundColor": "rgba(239,83,80,0.07)",
                    },
                    {
                        "if": {"filter_query": "{pnl} < 0", "column_id": "pnl"},
                        "color": "#ef5350",
                        "fontWeight": "600",
                    },
                    # Side column colouring
                    {
                        "if": {"filter_query": "{side} = long", "column_id": "side"},
                        "color": "#26a69a",
                    },
                    {
                        "if": {"filter_query": "{side} = short", "column_id": "side"},
                        "color": "#ef5350",
                    },
                    # Exit reason colouring
                    {
                        "if": {"filter_query": "{exit_reason} = tp", "column_id": "exit_reason"},
                        "color": "#26a69a",
                    },
                    {
                        "if": {"filter_query": "{exit_reason} = sl", "column_id": "exit_reason"},
                        "color": "#ef5350",
                    },
                    # Selected row highlight
                    {
                        "if": {"state": "selected"},
                        "backgroundColor": "rgba(249,168,37,0.15)",
                        "border": "1px solid #f9a825",
                    },
                ],
            ),
        ],
        style={"padding": "16px"},
    )
