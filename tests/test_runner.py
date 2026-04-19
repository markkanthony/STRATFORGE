import unittest
from types import SimpleNamespace

from api.runner import build_run_config


class BuildRunConfigTests(unittest.TestCase):
    def test_uses_strategy_backtest_overrides_without_project_timeframe(self):
        project = SimpleNamespace(symbol="EURUSD")

        config = build_run_config(
            project=project,
            strategy_config={
                "backtest": {
                    "timeframe": "M15",
                    "capital": 25_000,
                }
            },
        )

        self.assertEqual(config["backtest"]["symbol"], "EURUSD")
        self.assertEqual(config["backtest"]["timeframe"], "M15")
        self.assertEqual(config["backtest"]["capital"], 25_000)


if __name__ == "__main__":
    unittest.main()
