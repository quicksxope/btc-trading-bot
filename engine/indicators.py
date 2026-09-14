"""Indicator registry."""

from __future__ import annotations

import pandas as pd


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


REGISTRY = {
    "EMA": lambda df, p: ema(df["close"], int(p.get("period", 20))),
    "RSI": lambda df, p: rsi(df["close"], int(p.get("period", 14))),
    "ATR": lambda df, p: atr(df, int(p.get("period", 14))),
}


def compute_indicator(name: str, df: pd.DataFrame, params: dict) -> pd.Series:
    key = name.upper()
    if key not in REGISTRY:
        raise ValueError(f"Unknown indicator: {name}")
    return REGISTRY[key](df, params)
