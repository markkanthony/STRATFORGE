"""
ui/callbacks/run_callbacks.py

Callback: store-selected-run → store-run-data
When the user clicks a run in the sidebar, load the full JSON.
"""

from dash import Input, Output, no_update
from ui.data.loader import load_run_json


def register(app):
    @app.callback(
        Output("store-run-data", "data"),
        Input("store-selected-run", "data"),
    )
    def load_run_data(run_number):
        if run_number is None:
            return None
        return load_run_json(int(run_number))
