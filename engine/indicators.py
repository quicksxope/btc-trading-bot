"""Indicator registry with multi-output support."""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.bressert import bressert_dss
from engine.structure import fibonacci_levels, liquidity_sweep
from engine.wavetrend import wavetrend


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def stoch_rsi(
    series: pd.Series,
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_smooth: int = 3,
    d_smooth: int = 3,
) -> tuple[pd.Series, pd.Series]:
    r = rsi(series, rsi_period)
    lo = r.rolling(stoch_period).min()
    hi = r.rolling(stoch_period).max()
    stoch = 100 * (r - lo) / (hi - lo).replace(0, pd.NA)
    k = stoch.rolling(k_smooth).mean()
    d = k.rolling(d_smooth).mean()
    return k, d


def adx_dmi(
    df: pd.DataFrame,
    period: int = 14,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    high, low, close = df["high"], df["low"], df["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr_w = tr.ewm(alpha=1 / period, adjust=False).mean()
    atr_safe = atr_w.replace(0, np.nan)
    plus_di = (100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_safe).astype(float)
    minus_di = (100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_safe).astype(float)
    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = ((plus_di - minus_di).abs() / di_sum * 100).astype(float)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx, plus_di, minus_di


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def compute_indicator_outputs(name: str, df: pd.DataFrame, params: dict) -> dict[str, pd.Series]:
    """Return named output series for DSL refs (e.g. primary_RSI_value)."""
    key = name.upper()
    p = params or {}
    if key == "EMA":
        return {"value": ema(df["close"], int(p.get("period", 20)))}
    if key == "RSI":
        return {"value": rsi(df["close"], int(p.get("period", 14)))}
    if key == "ATR":
        return {"value": atr(df, int(p.get("period", 14)))}
    if key == "MACD":
        m, s, h = macd(
            df["close"],
            int(p.get("fast", 12)),
            int(p.get("slow", 26)),
            int(p.get("signal", 9)),
        )
        return {"macd": m, "signal": s, "hist": h}
    if key == "WAVETREND":
        wt, sig = wavetrend(
            df["high"],
            df["low"],
            df["close"],
            int(p.get("channel_length", 9)),
            int(p.get("average_length", 12)),
            int(p.get("signal_length", 4)),
        )
        return {"wt": wt, "signal": sig}
    if key == "BRESSERT":
        dss, sig = bressert_dss(
            df["high"],
            df["low"],
            df["close"],
            int(p.get("length", 8)),
            int(p.get("smoothing", 3)),
            int(p.get("signal_smoothing", 3)),
        )
        return {"dss": dss, "signal": sig}
    if key == "STOCHRSI":
        k, d = stoch_rsi(
            df["close"],
            int(p.get("rsi_period", 14)),
            int(p.get("stoch_period", 14)),
            int(p.get("k_smooth", 3)),
            int(p.get("d_smooth", 3)),
        )
        return {"k": k, "d": d}
    if key == "ADX":
        adx, pdi, mdi = adx_dmi(df, int(p.get("period", 14)))
        return {"adx": adx, "plus_di": pdi, "minus_di": mdi}
    if key == "FIB":
        return fibonacci_levels(
            df,
            int(p.get("leg_lookback", 20)),
            float(p.get("band_pct", 0.15)),
        )
    if key == "LIQUIDITYSWEEP":
        return liquidity_sweep(df, int(p.get("pool_lookback", 20)))
    raise ValueError(f"Unknown indicator: {name}")


def compute_indicator(name: str, df: pd.DataFrame, params: dict) -> pd.Series:
    outputs = compute_indicator_outputs(name, df, params)
    from engine.catalog import indicator_meta

    meta = indicator_meta(name.upper())
    out_key = meta.get("default_output") or next(iter(outputs))
    return outputs[out_key]
