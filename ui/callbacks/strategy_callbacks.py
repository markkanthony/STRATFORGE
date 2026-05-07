"""
ui/callbacks/strategy_callbacks.py

All callbacks for the 3-mode strategy workshop section:
  Mode 1 — copy-paste prompt workflow
  Mode 2 — Claude API agent (generate + preview + apply)
  Mode 3 — fully automated ai_loop.py
"""

import threading
from dash import Input, Output, State, no_update, ctx, html
import dash_bootstrap_components as dbc

_CARD2  = "#0f1624"
_BORDER = "#1e2d47"
_BLUE   = "#3b82f6"
_TEAL   = "#14b8a6"
_RED    = "#ef4444"
_MUTED  = "#64748b"
_TEXT   = "#e2e8f0"
_GREEN  = "#22c55e"
_AMBER  = "#f59e0b"

# ── Module-level state ───────────────────────────────────────────── #

_loop_status: dict = {
    "running": False,
    "iteration": 0,
    "max_iter": 20,
    "best_sharpe": None,
    "stop_reason": None,
    "error": None,
}

_agent_running: bool = False


# ── Helpers ──────────────────────────────────────────────────────── #

def _error_alert(message: str) -> dbc.Alert:
    return dbc.Alert(
        [html.B("Error: "), message],
        color="danger",
        style={"fontSize": "12px", "padding": "8px 12px", "marginTop": "6px"},
    )


def _code_preview(change_type: str, text: str) -> html.Div:
    label = "Config (YAML)" if change_type == "config" else "Code (Python)"
    color = _TEAL if change_type == "config" else _AMBER
    return html.Div([
        html.Div(label, style={"fontSize": "10px", "color": color, "fontWeight": "700",
                               "letterSpacing": "0.08em", "textTransform": "uppercase",
                               "marginBottom": "6px"}),
        html.Pre(text, style={
            "fontSize": "11px",
            "color": _TEXT,
            "background": _CARD2,
            "border": f"1px solid {_BORDER}",
            "borderRadius": "6px",
            "padding": "10px 12px",
            "maxHeight": "200px",
            "overflowY": "auto",
            "whiteSpace": "pre-wrap",
            "wordBreak": "break-word",
            "margin": 0,
        }),
    ])


def _mode_btn_style(active: bool) -> dict:
    color = _BLUE if active else _MUTED
    return {
        "background": f"{color}15" if active else "transparent",
        "color": color,
        "border": f"1px solid {color}{'55' if active else '22'}",
        "borderRadius": "6px",
        "padding": "7px 18px",
        "fontSize": "12px",
        "fontWeight": "700",
        "cursor": "pointer",
        "letterSpacing": "0.03em",
    }


def _start_backtest_thread() -> None:
    """Start a backtest in the background (reuses backtest_callbacks state)."""
    from ui.callbacks import backtest_callbacks as _bc
    if not _bc._status["running"]:
        _bc._status["running"] = True
        _bc._status["result"] = None
        _bc._status["error"] = None
        t = threading.Thread(target=_bc._run_backtest_worker, daemon=True)
        t.start()


# ── Register callbacks ────────────────────────────────────────────── #

def register(app):

    # ── Mode tab switching ────────────────────────────────────────── #
    @app.callback(
        Output("strategy-panel-1", "style"),
        Output("strategy-panel-2", "style"),
        Output("strategy-panel-3", "style"),
        Output("strategy-mode-btn-1", "style"),
        Output("strategy-mode-btn-2", "style"),
        Output("strategy-mode-btn-3", "style"),
        Input("strategy-mode-btn-1", "n_clicks"),
        Input("strategy-mode-btn-2", "n_clicks"),
        Input("strategy-mode-btn-3", "n_clicks"),
        prevent_initial_call=False,
    )
    def switch_mode(*_):
        triggered = ctx.triggered_id or "strategy-mode-btn-1"
        btn_ids = ["strategy-mode-btn-1", "strategy-mode-btn-2", "strategy-mode-btn-3"]
        active = btn_ids.index(triggered) if triggered in btn_ids else 0
        panels = [{"display": "block" if i == active else "none"} for i in range(3)]
        btns   = [_mode_btn_style(i == active) for i in range(3)]
        return *panels, *btns

    # ── Refresh prompt when section opens or run data changes ──────── #
    @app.callback(
        Output("strategy-prompt-pre", "children"),
        Input("store-project-section", "data"),
        Input("store-run-data", "data"),
    )
    def refresh_prompt(section, _run_data):
        if section != "strategy":
            return no_update
        from ui.data.projects import load_config, load_strategy_history, build_strategy_prompt
        config = load_config()
        history = load_strategy_history()
        return build_strategy_prompt(config, history)

    # ── Refresh history table ─────────────────────────────────────── #
    @app.callback(
        Output("strategy-history-table", "children"),
        Input("store-project-section", "data"),
        Input("store-run-data", "data"),
    )
    def refresh_history(section, _run_data):
        from ui.data.projects import load_strategy_history
        from ui.pages.strategy_view import _build_history_table
        history = load_strategy_history()
        return _build_history_table(history)

    # ── Mode 1: Apply & Run ───────────────────────────────────────── #
    @app.callback(
        Output("strategy-apply-status-1", "children"),
        Output("strategy-apply-status-1", "style"),
        Output("strategy-apply-errors-1", "children"),
        Output("btn-run-backtest", "disabled", allow_duplicate=True),
        Output("poll-interval", "disabled", allow_duplicate=True),
        Input("strategy-apply-btn-1", "n_clicks"),
        State("strategy-paste-area", "value"),
        prevent_initial_call=True,
    )
    def apply_mode1(_n, paste_text):
        base_style = {"fontSize": "12px", "marginLeft": "12px"}

        if not paste_text or not paste_text.strip():
            return "⚠ Nothing to apply", {**base_style, "color": _AMBER}, None, no_update, no_update

        from ui.data.projects import parse_ai_output, apply_ai_output
        parsed = parse_ai_output(paste_text)

        if parsed["type"] == "error":
            return ("✗ Parse error", {**base_style, "color": _RED},
                    _error_alert(parsed["message"]), no_update, no_update)

        try:
            apply_ai_output(parsed)
        except Exception as exc:
            return ("✗ Apply failed", {**base_style, "color": _RED},
                    _error_alert(str(exc)), no_update, no_update)

        _start_backtest_thread()
        return "⏳ Running…", {**base_style, "color": _BLUE}, None, True, False

    # ── Mode 2: Generate with Claude ─────────────────────────────── #
    @app.callback(
        Output("strategy-generate-status", "children"),
        Output("strategy-generate-status", "style"),
        Output("strategy-generate-preview", "children"),
        Output("strategy-apply-btn-2", "disabled"),
        Output("strategy-apply-btn-2", "style"),
        Output("store-agent-output", "data"),
        Input("strategy-generate-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def run_mode2_agent(_n):
        global _agent_running

        base_style = {"fontSize": "12px", "marginLeft": "12px"}
        disabled_btn = {
            "background": f"{_BLUE}1a", "color": _BLUE,
            "border": f"1px solid {_BLUE}55", "borderRadius": "6px",
            "padding": "7px 16px", "fontSize": "13px", "fontWeight": "600",
            "cursor": "not-allowed", "opacity": "0.5",
        }
        enabled_btn = {**disabled_btn, "cursor": "pointer", "opacity": "1"}

        if _agent_running:
            return ("Already running…", {**base_style, "color": _AMBER},
                    no_update, True, disabled_btn, no_update)

        from ui.data.projects import load_config, load_strategy_history, build_strategy_prompt, parse_ai_output
        config  = load_config()
        history = load_strategy_history()
        prompt  = build_strategy_prompt(config, history)

        _agent_running = True
        try:
            from anthropic import Anthropic
            client = Anthropic()
            message = client.messages.create(
                model="claude-opus-4-7",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = message.content[0].text
        except Exception as exc:
            _agent_running = False
            return (f"✗ {str(exc)[:80]}", {**base_style, "color": _RED},
                    _error_alert(str(exc)), True, disabled_btn, None)
        finally:
            _agent_running = False

        parsed = parse_ai_output(response_text)

        if parsed["type"] == "error":
            return ("✗ Parse error", {**base_style, "color": _RED},
                    _error_alert(parsed["message"]), True, disabled_btn, None)

        import yaml
        preview_text = (
            yaml.dump(parsed["strategy"], default_flow_style=False)
            if parsed["type"] == "config"
            else parsed["code"]
        )
        from ui.callbacks.strategy_callbacks import _code_preview
        preview = _code_preview(parsed["type"], preview_text)

        return ("✓ Ready to apply", {**base_style, "color": _GREEN},
                preview, False, enabled_btn, parsed)

    # ── Mode 2: Apply & Run ───────────────────────────────────────── #
    @app.callback(
        Output("strategy-apply-status-2", "children"),
        Output("strategy-apply-status-2", "style"),
        Output("strategy-apply-errors-2", "children"),
        Output("btn-run-backtest", "disabled", allow_duplicate=True),
        Output("poll-interval", "disabled", allow_duplicate=True),
        Input("strategy-apply-btn-2", "n_clicks"),
        State("store-agent-output", "data"),
        prevent_initial_call=True,
    )
    def apply_mode2(_n, parsed):
        base_style = {"fontSize": "12px", "marginLeft": "12px"}
        if not parsed:
            return "⚠ Nothing to apply", {**base_style, "color": _AMBER}, None, no_update, no_update

        from ui.data.projects import apply_ai_output
        try:
            apply_ai_output(parsed)
        except Exception as exc:
            return ("✗ Apply failed", {**base_style, "color": _RED},
                    _error_alert(str(exc)), no_update, no_update)

        _start_backtest_thread()
        return "⏳ Running…", {**base_style, "color": _BLUE}, None, True, False

    # ── Mode 3: Start loop ────────────────────────────────────────── #
    @app.callback(
        Output("strategy-loop-start-btn", "disabled"),
        Output("strategy-loop-stop-btn",  "disabled"),
        Output("strategy-loop-status",    "children"),
        Output("strategy-loop-status",    "style"),
        Output("strategy-loop-interval",  "disabled"),
        Input("strategy-loop-start-btn", "n_clicks"),
        State("strategy-loop-max-iter", "value"),
        prevent_initial_call=True,
    )
    def start_loop(_n, max_iter):
        global _loop_status
        running_style = {"color": _BLUE, "fontSize": "13px", "fontFamily": "monospace"}

        if _loop_status["running"]:
            return True, False, "Already running…", running_style, False

        _loop_status = {
            "running": True,
            "iteration": 0,
            "max_iter": int(max_iter or 20),
            "best_sharpe": None,
            "stop_reason": None,
            "error": None,
        }

        def _loop_worker():
            global _loop_status
            try:
                from ai_loop import AIOptimizerLoop
                loop = AIOptimizerLoop(max_iterations=_loop_status["max_iter"])

                original_update = loop._update_tracking
                def _patched(run_data):
                    original_update(run_data)
                    _loop_status["iteration"] = len(loop.history)
                    _loop_status["best_sharpe"] = (
                        loop.best_val_sharpe if loop.best_val_sharpe != float("-inf") else None
                    )
                    if not _loop_status["running"]:
                        raise StopIteration("stopped by user")
                loop._update_tracking = _patched

                summary = loop.run()
                _loop_status["stop_reason"] = summary.get("stop_reason")
            except StopIteration:
                _loop_status["stop_reason"] = "Stopped by user"
            except Exception as exc:
                _loop_status["error"] = str(exc)
            finally:
                _loop_status["running"] = False

        threading.Thread(target=_loop_worker, daemon=True).start()
        return True, False, "⏳ Starting…", running_style, False

    # ── Mode 3: Stop loop ─────────────────────────────────────────── #
    @app.callback(
        Output("strategy-loop-start-btn", "disabled", allow_duplicate=True),
        Output("strategy-loop-stop-btn",  "disabled", allow_duplicate=True),
        Output("strategy-loop-status",    "children", allow_duplicate=True),
        Output("strategy-loop-status",    "style",    allow_duplicate=True),
        Output("strategy-loop-interval",  "disabled", allow_duplicate=True),
        Input("strategy-loop-stop-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def stop_loop(_n):
        global _loop_status
        _loop_status["running"] = False
        return False, True, "● Stopped", {"color": _MUTED, "fontSize": "13px", "fontFamily": "monospace"}, True

    # ── Mode 3: Poll loop status ──────────────────────────────────── #
    @app.callback(
        Output("strategy-loop-status",    "children", allow_duplicate=True),
        Output("strategy-loop-status",    "style",    allow_duplicate=True),
        Output("strategy-loop-start-btn", "disabled", allow_duplicate=True),
        Output("strategy-loop-stop-btn",  "disabled", allow_duplicate=True),
        Output("strategy-loop-interval",  "disabled", allow_duplicate=True),
        Input("strategy-loop-interval", "n_intervals"),
        prevent_initial_call=True,
    )
    def poll_loop(_n):
        global _loop_status
        mono = {"fontSize": "13px", "fontFamily": "monospace"}

        if _loop_status["running"]:
            it = _loop_status["iteration"]
            mx = _loop_status["max_iter"]
            bs = _loop_status["best_sharpe"]
            sharpe = f" · Best Sharpe {bs:.3f}" if bs is not None else ""
            return (f"⏳ Iteration {it}/{mx}{sharpe}", {**mono, "color": _BLUE},
                    True, False, False)

        if _loop_status.get("error"):
            return (f"✗ {_loop_status['error'][:100]}", {**mono, "color": _RED},
                    False, True, True)

        if _loop_status.get("stop_reason"):
            bs = _loop_status.get("best_sharpe")
            sharpe = f" · Best Sharpe {bs:.3f}" if bs is not None else ""
            return (f"✓ {_loop_status['stop_reason']}{sharpe}", {**mono, "color": _GREEN},
                    False, True, True)

        return "● Ready", {**mono, "color": _MUTED}, False, True, True
