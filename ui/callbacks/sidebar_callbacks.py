"""
ui/callbacks/sidebar_callbacks.py

Callbacks for sidebar interactions:
  - Run card click → store-selected-run
  - Window toggle → store-selected-window
  - store-run-data → metrics panel update
  - Tab + run/window change → tab content rendering
  - Dashboard table row click → store-selected-run + switch to Chart tab
"""

from dash import Input, Output, State, ALL, ctx, no_update
import dash_bootstrap_components as dbc

from ui.components.metrics_panel import build_metrics_panel


def register(app):

    # ---- Run list item click → store-selected-run ------------------ #
    @app.callback(
        Output("store-selected-run", "data", allow_duplicate=True),
        Output("sidebar-run-list", "children", allow_duplicate=True),
        Input({"type": "run-list-item", "index": ALL}, "n_clicks"),
        State("store-selected-run", "data"),
        prevent_initial_call=True,
    )
    def on_run_click(n_clicks_list, current_run):
        if not any(n_clicks_list):
            return no_update, no_update

        triggered = ctx.triggered_id
        if triggered is None:
            return no_update, no_update

        new_run = triggered["index"]
        from ui.components.run_selector import build_run_list_items
        return new_run, build_run_list_items(new_run)

    # ---- Window toggle → store-selected-window --------------------- #
    @app.callback(
        Output("store-selected-window", "data"),
        Input("window-toggle", "value"),
    )
    def on_window_toggle(value):
        return value or "validation"

    # ---- Metrics panel refresh on run or window change ------------- #
    @app.callback(
        Output("metrics-panel-container", "children"),
        Input("store-run-data", "data"),
    )
    def update_metrics(run_data):
        return build_metrics_panel(run_data)

    # ---- Tab content renderer -------------------------------------- #
    @app.callback(
        Output("tab-content", "children"),
        Input("main-tabs", "active_tab"),
    )
    def render_tab(active_tab):
        from ui.pages.dashboard import build_dashboard_layout
        from ui.pages.chart import build_chart_layout
        from ui.pages.journal import build_journal_layout

        if active_tab == "tab-chart":
            return build_chart_layout()
        if active_tab == "tab-journal":
            return build_journal_layout()
        return build_dashboard_layout()

    # ---- Dashboard table row click → select run + go to Chart ------ #
    @app.callback(
        Output("store-selected-run", "data", allow_duplicate=True),
        Output("main-tabs", "active_tab"),
        Output("sidebar-run-list", "children", allow_duplicate=True),
        Input("dashboard-runs-table", "selected_rows"),
        State("dashboard-runs-table", "data"),
        prevent_initial_call=True,
    )
    def on_dashboard_row_click(selected_rows, table_data):
        if not selected_rows or not table_data:
            return no_update, no_update, no_update
        row = table_data[selected_rows[0]]
        run_num = row.get("run")
        if run_num is None:
            return no_update, no_update, no_update
        from ui.components.run_selector import build_run_list_items
        return run_num, "tab-chart", build_run_list_items(run_num)
