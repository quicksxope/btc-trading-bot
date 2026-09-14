"""WaveTrend oscillator (Cipher B-style core)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def wavetrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    channel_length: int = 9,
    average_length: int = 12,
    signal_length: int = 4,
) -> tuple[pd.Series, pd.Series]:
    average_price = (high + low + close) / 3.0
    esa = average_price.ewm(span=channel_length, adjust=False).mean()
    deviation = (average_price - esa).abs().ewm(span=channel_length, adjust=False).mean()
    composite_index = (average_price - esa) / (0.015 * deviation.replace(0, np.nan))
    wave_trend = composite_index.fillna(0.0).ewm(span=average_length, adjust=False).mean()
    signal = wave_trend.rolling(signal_length, min_periods=1).mean()
    return wave_trend, signal
