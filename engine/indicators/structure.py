"""Fibonacci levels and liquidity sweep flags (OHLCV)."""

from __future__ import annotations

import pandas as pd


def fibonacci_levels(
    df: pd.DataFrame,
    leg_lookback: int = 20,
    band_pct: float = 0.15,
) -> dict[str, pd.Series]:
    """Retrace levels from rolling leg high/low; `near_*` flags close in band."""
    high = df["high"].rolling(leg_lookback, min_periods=leg_lookback).max()
    low = df["low"].rolling(leg_lookback, min_periods=leg_lookback).min()
    span = (high - low).replace(0, pd.NA)
    level_382 = high - 0.382 * span
    level_618 = high - 0.618 * span
    band = span * band_pct
    near_382 = ((df["close"] - level_382).abs() <= band).astype(float)
    near_618 = ((df["close"] - level_618).abs() <= band).astype(float)
    return {
        "level_382": level_382,
        "level_618": level_618,
        "near_382": near_382,
        "near_618": near_618,
    }


def liquidity_sweep(
    df: pd.DataFrame,
    pool_lookback: int = 20,
) -> dict[str, pd.Series]:
    """Bull/bear sweep: pierce prior pool then close back inside (prior bar window)."""
    prior_high = df["high"].shift(1).rolling(pool_lookback, min_periods=pool_lookback).max()
    prior_low = df["low"].shift(1).rolling(pool_lookback, min_periods=pool_lookback).min()
    sweep_bull = ((df["low"] < prior_low) & (df["close"] > prior_low)).astype(float)
    sweep_bear = ((df["high"] > prior_high) & (df["close"] < prior_high)).astype(float)
    return {"sweep_bull": sweep_bull, "sweep_bear": sweep_bear}
