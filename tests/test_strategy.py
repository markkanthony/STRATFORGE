import unittest

import pandas as pd

from strategy import (
    build_context_features,
    build_indicator_features,
    build_pattern_features,
    build_rule_features,
    evaluate_rules,
    validate_entry_code_source,
)


class MultiTimeframeStrategyTests(unittest.TestCase):
    def test_higher_timeframe_trend_is_projected_onto_base_bars(self):
        df = pd.DataFrame(
            {
                "time": pd.date_range("2026-01-01 00:00:00", periods=12, freq="1h", tz="UTC"),
                "open": [float(value) for value in range(1, 13)],
                "high": [float(value) + 0.3 for value in range(1, 13)],
                "low": [float(value) - 0.3 for value in range(1, 13)],
                "close": [float(value) for value in range(1, 13)],
            }
        )
        config = {
            "backtest": {"timeframe": "H1"},
            "strategy": {
                "indicators": {
                    "fast_ema": 1,
                    "slow_ema": 2,
                    "rsi_period": 14,
                    "atr_period": 14,
                },
                "context": {
                    "trend_filter": "ema",
                    "use_higher_timeframe": True,
                    "higher_timeframe": "H4",
                },
            },
        }

        result = build_context_features(build_indicator_features(df.copy(), config), config)

        self.assertTrue((result.loc[result.index[:8], "trend_up"] == False).all())
        self.assertTrue((result.loc[result.index[8:], "trend_up"] == True).all())
        self.assertTrue((result["trend_down"] == False).all())

    def test_explicit_rule_columns_cover_ema_rsi_bollinger_and_sessions(self):
        df = pd.DataFrame(
            {
                "time": pd.date_range("2026-01-01 06:00:00", periods=4, freq="1h", tz="UTC"),
                "open": [100.0, 100.5, 101.0, 107.0],
                "high": [101.0, 101.5, 104.0, 111.0],
                "low": [99.0, 100.0, 100.5, 106.0],
                "close": [100.0, 100.4, 104.0, 110.0],
                "ema_fast": [1.0, 1.0, 3.0, 4.0],
                "ema_slow": [2.0, 2.0, 2.0, 3.0],
                "ema_trend": [3.0, 3.0, 1.0, 1.0],
                "rsi": [45.0, 48.0, 62.0, 74.0],
                "bb_upper": [105.0, 105.0, 105.0, 108.0],
                "bb_lower": [95.0, 95.0, 95.0, 92.0],
                "bb_mid": [100.0, 100.0, 100.0, 101.0],
                "session": ["asia", "asia", "london", "london"],
            }
        )

        result = build_rule_features(df)

        self.assertTrue(result.loc[result.index[-1], "ema_fast_crosses_above_slow"])
        self.assertTrue(result.loc[result.index[-1], "ema_bull_stack_3"])
        self.assertTrue(result.loc[result.index[-1], "rsi_above_70"])
        self.assertTrue(result.loc[result.index[-1], "bb_close_above_upper"])
        self.assertTrue(result.loc[result.index[-1], "session_london"])

    def test_python_entry_code_generates_signal_masks(self):
        df = pd.DataFrame(
            {
                "ema_fast": [1.0, 3.0, 1.0],
                "ema_slow": [2.0, 2.0, 2.0],
                "rsi": [40.0, 60.0, 35.0],
            }
        )
        config = {
            "strategy": {
                "entry_code": """
def generate_entry(df):
    long_mask = (df["ema_fast"] > df["ema_slow"]) & (df["rsi"] > 50)
    short_mask = (df["ema_fast"] < df["ema_slow"]) & (df["rsi"] < 50)
    return long_mask, short_mask
""".strip(),
            }
        }

        result = evaluate_rules(df.copy(), config)

        self.assertEqual(result["signal"].tolist(), [-1, 1, -1])

    def test_validate_entry_code_rejects_syntax_error(self):
        with self.assertRaisesRegex(ValueError, "syntax error"):
            validate_entry_code_source("def generate_entry(df)\n    return df['close'] > 0, df['close'] < 0")

    def test_validate_entry_code_requires_generate_entry(self):
        with self.assertRaisesRegex(ValueError, "define generate_entry"):
            validate_entry_code_source("x = 1")

    def test_evaluate_rules_rejects_invalid_return_shape(self):
        df = pd.DataFrame({"close": [1.0, 2.0]})
        config = {
            "strategy": {
                "entry_code": """
def generate_entry(df):
    return df["close"] > 1
""".strip(),
            }
        }

        with self.assertRaisesRegex(ValueError, "tuple of \\(long_mask, short_mask\\)"):
            evaluate_rules(df, config)

    def test_evaluate_rules_rejects_non_boolean_output(self):
        df = pd.DataFrame({"close": [1.0, 2.0]})
        config = {
            "strategy": {
                "entry_code": """
def generate_entry(df):
    return df["close"], df["close"]
""".strip(),
            }
        }

        with self.assertRaisesRegex(ValueError, "must contain only boolean values"):
            evaluate_rules(df, config)

    def test_evaluate_rules_rejects_mask_length_mismatch(self):
        df = pd.DataFrame({"close": [1.0, 2.0, 3.0]})
        config = {
            "strategy": {
                "entry_code": """
def generate_entry(df):
    return [True, False], [False, True]
""".strip(),
            }
        }

        with self.assertRaisesRegex(ValueError, "length does not match"):
            evaluate_rules(df, config)

    def test_python_entry_code_can_use_built_columns(self):
        df = pd.DataFrame(
            {
                "time": pd.date_range("2026-01-01 00:00:00", periods=5, freq="1h", tz="UTC"),
                "open": [1.1000, 1.1010, 1.1005, 1.1008, 1.1006],
                "high": [1.1010, 1.1020, 1.1040, 1.1015, 1.1012],
                "low": [1.0990, 1.1000, 1.1000, 1.0998, 1.0997],
                "close": [1.1005, 1.1015, 1.1035, 1.1004, 1.1002],
                "volume": [100, 120, 150, 110, 90],
            }
        )
        config = {
            "backtest": {"timeframe": "H1"},
            "strategy": {
                "indicators": {
                    "fast_ema": 2,
                    "slow_ema": 3,
                    "trend_ema": 4,
                    "rsi_period": 2,
                    "atr_period": 2,
                    "bollinger_period": 2,
                    "bollinger_std": 2,
                },
                "patterns": {
                    "orb": {"enabled": True, "bars": 2},
                },
                "context": {
                    "use_prev_day_levels": True,
                    "use_session_filter": True,
                },
                "entry_code": """
def generate_entry(df):
    required = ["ema_fast", "ema_slow", "ema_trend", "rsi", "atr", "bb_mid", "bb_upper", "bb_lower", "session", "prev_day_high", "prev_day_low", "orb_breakout_long"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    long_mask = df["orb_breakout_long"] & df["session"].eq("asia")
    short_mask = pd.Series(False, index=df.index)
    return long_mask.fillna(False), short_mask
""".strip(),
            },
        }

        result = build_indicator_features(df.copy(), config)
        result = build_pattern_features(result, config)
        result = build_context_features(result, config)
        result = build_rule_features(result)
        result = evaluate_rules(result, config)

        self.assertTrue(result.loc[result.index[2], "orb_breakout_long"])
        self.assertEqual(result.loc[result.index[2], "signal"], 1)


if __name__ == "__main__":
    unittest.main()
