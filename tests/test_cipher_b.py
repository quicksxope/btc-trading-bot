import numpy as np
import pandas as pd

from engine.strategy import cipher_b_signals


def test_cipher_b_signals_shape_and_values():
    n = 200
    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="30min"),
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1.0,
        }
    )
    sig = cipher_b_signals(df)
    assert len(sig) == n
    assert set(sig.unique()).issubset({-1, 0, 1})
