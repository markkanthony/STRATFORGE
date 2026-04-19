"""
ui/app.py — StratForge Web UI entry point.

Run from the project root:
    python ui/app.py

Then open: http://127.0.0.1:8081
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so `core`, `strategy`, `run` imports work
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Also ensure the ui package itself resolves from root
_UI_PARENT = Path(__file__).parent.parent
if str(_UI_PARENT) not in sys.path:
    sys.path.insert(0, str(_UI_PARENT))

import dash
import dash_bootstrap_components as dbc

from ui.layout import build_layout
from ui.callbacks import (
    run_callbacks,
    chart_callbacks,
    journal_callbacks,
    backtest_callbacks,
    sidebar_callbacks,
    nav_callbacks,
)


def create_app() -> dash.Dash:
    app = dash.Dash(
        __name__,
        external_stylesheets=[
            dbc.themes.DARKLY,
            # Inter font for clean typography
            "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap",
            # Bootstrap Icons for nav icons
            "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
        ],
        suppress_callback_exceptions=True,  # sections render lazily
        title="StratForge",
        update_title=None,
    )

    app.layout = build_layout()

    # Register all callbacks
    run_callbacks.register(app)
    chart_callbacks.register(app)
    journal_callbacks.register(app)
    backtest_callbacks.register(app)
    sidebar_callbacks.register(app)
    nav_callbacks.register(app)

    return app


if __name__ == "__main__":
    host = "127.0.0.1"
    port = 8081
    app = create_app()
    print("=" * 60)
    print("  StratForge UI")
    print(f"  Dashboard: http://{host}:{port}")
    print("  Uses local results/ artifacts only")
    print("=" * 60)
    app.run(
        debug=False,          # set True for dev hot-reload (requires main thread)
        host=host,
        port=port,
        use_reloader=False,   # reloader requires signal module (unavailable on Windows subprocesses)
    )
