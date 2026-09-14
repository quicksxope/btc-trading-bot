"""Simple built-in strategy presets."""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.indicators import ema, rsi


def trend_ema_cross_signals(primary: pd.DataFrame) -> pd.Series:
    close = primary["close"]
    fast = ema(close, 20)
    slow = ema(close, 50)
    sig = np.where(fast > slow, 1, np.where(fast < slow, -1, 0))
    return pd.Series(sig, index=primary.index)


def rsi_mean_revert_signals(primary: pd.DataFrame) -> pd.Series:
    close = primary["close"]
    r = rsi(close, 14)
    sig = np.where(r < 30, 1, np.where(r > 70, -1, 0))
    return pd.Series(sig, index=primary.index)
