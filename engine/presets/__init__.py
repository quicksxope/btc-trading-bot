"""Named strategy presets for wizard and YAML."""

from __future__ import annotations

import pandas as pd

from engine.presets.builtins import rsi_mean_revert_signals, trend_ema_cross_signals
from engine.presets.cipher_b import cipher_b_signals

PRESET_IDS = frozenset({"trend_ema_cross", "rsi_mean_revert", "cipher_b"})


def preset_signals(name: str, primary: pd.DataFrame) -> pd.Series:
    """1 long, -1 short, 0 flat."""
    if name == "trend_ema_cross":
        return trend_ema_cross_signals(primary)
    if name == "rsi_mean_revert":
        return rsi_mean_revert_signals(primary)
    if name == "cipher_b":
        return cipher_b_signals(primary)
    raise ValueError(f"Unknown preset: {name}")


__all__ = [
    "PRESET_IDS",
    "cipher_b_signals",
    "preset_signals",
    "rsi_mean_revert_signals",
    "trend_ema_cross_signals",
]
