import numpy as np
import pandas as pd

from engine.indicators import compute_indicator_outputs
from engine.rules import RuleSet, signals_from_rules, validate_expression


def _ohlcv(n=120):
    close = 100 + np.cumsum(np.random.default_rng(2).normal(0, 0.4, n))
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 100.0,
        }
    )


def test_new_indicator_outputs():
    df = _ohlcv()
    for name, params in (
        ("STOCHRSI", {}),
        ("ADX", {}),
        ("FIB", {}),
        ("LIQUIDITYSWEEP", {}),
    ):
        out = compute_indicator_outputs(name, df, params)
        assert out
        for ser in out.values():
            assert len(ser) == len(df)


def test_adx_dsl_template():
    validate_expression("primary_ADX_adx > 25")
    df = _ohlcv(80)
    specs = [{"name": "ADX", "timeframe": "primary", "params": {"period": 14}}]
    sig = signals_from_rules(
        RuleSet(long_when="primary_ADX_adx > 10", short_when="primary_ADX_adx > 10"),
        df,
        {},
        {},
        specs,
    )
    assert len(sig) == len(df)
