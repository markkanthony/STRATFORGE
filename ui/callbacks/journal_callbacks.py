"""
ui/callbacks/journal_callbacks.py

Callbacks for the Trade Journal tab:
  1. Populate DataTable when run-data or window changes
  2. Trade row selection → store-highlighted-trade-idx → chart zoom
"""

from dash import Input, Output, State, no_update

from ui.data.loader import get_trades
from ui.pages.journal import trades_to_table_rows


def register(app):

    # ---- Populate table ------------------------------------------- #
    @app.callback(
        Output("trade-journal-table", "data"),
        Output("trade-journal-table", "selected_rows"),
        Input("store-run-data", "data"),
        Input("store-selected-window", "data"),
    )
    def populate_journal(run_data, window):
        if not run_data:
            return [], []
        window = window or "validation"
        trades = get_trades(run_data, window)
        rows = trades_to_table_rows(trades)
        return rows, []

    # ---- Row click → highlight store ------------------------------- #
    @app.callback(
        Output("store-highlighted-trade-idx", "data"),
        Input("trade-journal-table", "selected_rows"),
        State("trade-journal-table", "data"),
    )
    def on_trade_selected(selected_rows, table_data):
        if not selected_rows or not table_data:
            return None
        row = table_data[selected_rows[0]]
        return row.get("trade_idx")
