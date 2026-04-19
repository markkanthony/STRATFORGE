"""
ui/callbacks/backtest_callbacks.py

Callbacks for the "Run New Backtest" button.
Uses a background thread so Dash stays responsive during the run.
A dcc.Interval polls every 2 s for completion.
"""

import threading
from dash import Input, Output, State, no_update, ctx

# ---- Shared state (module-level, thread-safe for single-user use) -- #
_status = {
    "running": False,
    "result": None,   # run_data dict on success
    "error": None,    # error message string on failure
}


def _run_backtest_worker():
    global _status
    try:
        import sys
        from pathlib import Path
        root = Path(__file__).parent.parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        import run as _run_module
        import importlib
        importlib.reload(_run_module)
        result = _run_module.run_backtest_full()
        _status["result"] = result
        _status["error"] = None
    except Exception as exc:
        _status["result"] = None
        _status["error"] = str(exc)
    finally:
        _status["running"] = False


def register(app):

    # ---- Button click → start worker thread ------------------------ #
    @app.callback(
        Output("btn-run-backtest", "disabled"),
        Output("backtest-status-text", "children"),
        Output("poll-interval", "disabled"),
        Input("btn-run-backtest", "n_clicks"),
        prevent_initial_call=True,
    )
    def start_backtest(_n):
        global _status
        if _status["running"]:
            return True, "Already running…", False

        _status["running"] = True
        _status["result"]  = None
        _status["error"]   = None

        t = threading.Thread(target=_run_backtest_worker, daemon=True)
        t.start()

        return True, "⏳ Running…", False   # enable interval polling

    # ---- Interval poll → update sidebar on completion -------------- #
    @app.callback(
        Output("store-selected-run", "data"),
        Output("btn-run-backtest", "disabled", allow_duplicate=True),
        Output("backtest-status-text", "children", allow_duplicate=True),
        Output("poll-interval", "disabled", allow_duplicate=True),
        Output("sidebar-run-list", "children"),
        Input("poll-interval", "n_intervals"),
        State("store-selected-run", "data"),
        prevent_initial_call=True,
    )
    def poll_completion(_, current_run):
        global _status

        if _status["running"]:
            return no_update, no_update, "⏳ Running…", no_update, no_update

        if _status["error"]:
            err = _status["error"]
            _status["error"] = None
            return no_update, False, f"✗ {err[:60]}", True, no_update

        if _status["result"]:
            new_run = _status["result"]["run"]
            _status["result"] = None
            from ui.components.run_selector import build_run_list_items
            return new_run, False, f"✓ Run #{new_run} complete", True, build_run_list_items(new_run)

        # Nothing happened yet — disable interval if we're idle
        return no_update, False, "● Ready", True, no_update
