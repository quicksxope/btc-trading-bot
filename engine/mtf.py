"""Align higher timeframe series to primary bars (no lookahead)."""

from __future__ import annotations

import pandas as pd


def align_context_to_primary(primary: pd.DataFrame, context: pd.DataFrame) -> pd.Series:
    """For each primary bar, index of last context bar whose timestamp <= primary close."""
    ctx_ts = context["timestamp"].values
    idx = []
    j = -1
    for ts in primary["timestamp"].values:
        while j + 1 < len(ctx_ts) and ctx_ts[j + 1] <= ts:
            j += 1
        idx.append(j)
    return pd.Series(idx, index=primary.index)


def resample_bars(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    x = df.set_index("timestamp")
    o = x["open"].resample(rule).first()
    h = x["high"].resample(rule).max()
    l = x["low"].resample(rule).min()
    c = x["close"].resample(rule).last()
    v = x["volume"].resample(rule).sum()
    out = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": v}).dropna()
    return out.reset_index()
