"""Cipher B–style preset (WaveTrend + RSI + Bressert, VuManChu-inspired)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.indicators import bressert_dss, rsi, wavetrend


def _crossed_above(line: pd.Series, signal: pd.Series, i: int) -> bool:
    if i < 1:
        return False
    return float(line.iloc[i - 1]) <= float(signal.iloc[i - 1]) and float(line.iloc[i]) > float(
        signal.iloc[i]
    )


def _crossed_below(line: pd.Series, signal: pd.Series, i: int) -> bool:
    if i < 1:
        return False
    return float(line.iloc[i - 1]) >= float(signal.iloc[i - 1]) and float(line.iloc[i]) < float(
        signal.iloc[i]
    )


def cipher_b_signals(primary: pd.DataFrame) -> pd.Series:
    """WaveTrend cross + RSI + Bressert (Hola Prime folder defaults)."""
    high, low, close = primary["high"], primary["low"], primary["close"]
    wt, wt_sig = wavetrend(high, low, close, 9, 12, 4)
    r = rsi(close, 14)
    dss, dss_sig = bressert_dss(high, low, close, 8, 3, 3)

    n = len(primary)
    out = np.zeros(n, dtype=int)
    state = 0
    for i in range(1, n):
        long_cross = _crossed_above(wt, wt_sig, i)
        short_cross = _crossed_below(wt, wt_sig, i)
        rsi_long = float(r.iloc[i]) > 50.0
        rsi_short = float(r.iloc[i]) < 50.0
        bressert_long = float(dss.iloc[i]) > float(dss_sig.iloc[i])
        bressert_short = float(dss.iloc[i]) < float(dss_sig.iloc[i])
        if long_cross and rsi_long and bressert_long:
            state = 1
        elif short_cross and rsi_short and bressert_short:
            state = -1
        out[i] = state
    return pd.Series(out, index=primary.index)
