import numpy as np
import pandas as pd

from engine.models import CustomRulesV2, StrategyConfig
from engine.rules import RuleSet, signals_from_rules, validate_expression
from engine.strategy import build_signals


def _sample_df(n=100):
    close = 100 + np.cumsum(np.random.default_rng(1).normal(0, 0.3, n))
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1.0,
        }
    )


def test_validate_rsi_expression():
    validate_expression("primary_RSI_value < 30")


def test_validate_cross_above_with_comma():
    validate_expression("cross_above(primary_WAVETREND_wt, primary_WAVETREND_signal)")


def test_validate_and_with_cross_templates():
    expr = (
        "(cross_above(primary_BRESSERT_dss, primary_BRESSERT_signal)) "
        "and (primary_RSI_value < 30)"
    )
    validate_expression(expr)


def test_signals_from_rsi_rule():
    primary = _sample_df(80)
    specs = [{"name": "RSI", "timeframe": "primary", "params": {"period": 14}}]
    sig = signals_from_rules(
        RuleSet(long_when="primary_RSI_value < 35", short_when="primary_RSI_value > 65"),
        primary,
        {},
        {},
        specs,
    )
    assert len(sig) == len(primary)
    assert set(sig.unique()).issubset({-1, 0, 1})


def test_build_signals_custom_rules_v2():
    primary = _sample_df(60)
    cfg = StrategyConfig(
        mode="custom",
        custom_indicators=[{"name": "RSI", "timeframe": "primary", "params": {"period": 14}}],
        custom_rules_v2=CustomRulesV2(long_when="primary_RSI_value < 40", short_when=""),
    )
    sig = build_signals(cfg, primary, {}, {})
    assert len(sig) == len(primary)
