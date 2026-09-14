"""Bressert-style double smoothed stochastic."""

from __future__ import annotations

import pandas as pd


def bressert_dss(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 8,
    smoothing: int = 3,
    signal_smoothing: int = 3,
) -> tuple[pd.Series, pd.Series]:
    lowest_low = low.rolling(length, min_periods=1).min()
    highest_high = high.rolling(length, min_periods=1).max()
    range_ = (highest_high - lowest_low).replace(0, pd.NA)
    stochastic = 100 * (close - lowest_low) / range_
    smoothed_once = stochastic.fillna(50.0).ewm(span=smoothing, adjust=False).mean()
    dss = smoothed_once.ewm(span=smoothing, adjust=False).mean()
    signal = dss.ewm(span=signal_smoothing, adjust=False).mean()
    return dss, signal
