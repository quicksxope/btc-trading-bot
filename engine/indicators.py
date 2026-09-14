"""Indicator registry with multi-output support."""

from __future__ import annotations

import pandas as pd

from engine.bressert import bressert_dss
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
    raise ValueError(f"Unknown indicator: {name}")


def compute_indicator(name: str, df: pd.DataFrame, params: dict) -> pd.Series:
    outputs = compute_indicator_outputs(name, df, params)
    from engine.catalog import indicator_meta

    meta = indicator_meta(name.upper())
    out_key = meta.get("default_output") or next(iter(outputs))
    return outputs[out_key]
