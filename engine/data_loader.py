"""Load OHLCV bars from Supabase warehouse or local CSV fallback."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from engine.mtf import resample_bars
from engine.supabase_client import is_configured
from engine.warehouse import load_bars_range

# Coinbase Exchange has no native 30m candles — build from 15m.
RESAMPLE_FROM = {"30m": "15m"}

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "ohlcv"


def _load_bars_raw(data_symbol: str, timeframe: str, start, end) -> pd.DataFrame:
    if is_configured():
        df = load_bars_range(data_symbol, timeframe, start, end)
        if not df.empty:
            return df

    path = DATA_ROOT / data_symbol / f"{timeframe}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing data: {path} (and no Supabase rows for {data_symbol} {timeframe})"
        )
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    mask = (df["timestamp"].dt.date >= start) & (df["timestamp"].dt.date <= end)
    out = df.loc[mask].copy()
    if out.empty:
        raise ValueError(f"No bars in range for {data_symbol} {timeframe}")
    return out


def load_bars(data_symbol: str, timeframe: str, start, end) -> pd.DataFrame:
    source_tf = RESAMPLE_FROM.get(timeframe, timeframe)
    df = _load_bars_raw(data_symbol, source_tf, start, end)
    if timeframe in RESAMPLE_FROM:
        return resample_bars(df, "30min")
    return df
