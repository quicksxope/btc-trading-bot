"""Strategy signals from preset or custom rule (subset DSL)."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from engine.indicators import compute_indicator, ema, rsi
from engine.models import StrategyConfig


def preset_signals(name: str, primary: pd.DataFrame) -> pd.Series:
    """1 long, -1 short, 0 flat."""
    close = primary["close"]
    if name == "trend_ema_cross":
        fast = ema(close, 20)
        slow = ema(close, 50)
        sig = np.where(fast > slow, 1, np.where(fast < slow, -1, 0))
        return pd.Series(sig, index=primary.index)
    if name == "rsi_mean_revert":
        r = rsi(close, 14)
        sig = np.where(r < 30, 1, np.where(r > 70, -1, 0))
        return pd.Series(sig, index=primary.index)
    raise ValueError(f"Unknown preset: {name}")


def _eval_simple_rule(rule: str, ctx: dict[str, float]) -> int:
    """
    Templates: long if RSI<30, short if RSI>70, or AND clauses on ctx keys.
    ctx keys like primary_RSI, context_4h_close_gt_context_4h_EMA200 precomputed.
    """
    rule = rule.strip().lower()
    if rule in ("long", "short", "flat"):
        return {"long": 1, "short": -1, "flat": 0}[rule]
    if "rsi" in rule and "<" in rule:
        m = re.search(r"rsi\s*<\s*([\d.]+)", rule)
        if m and ctx.get("primary_RSI", 50) < float(m.group(1)):
            return 1
    if "rsi" in rule and ">" in rule:
        m = re.search(r"rsi\s*>\s*([\d.]+)", rule)
        if m and ctx.get("primary_RSI", 50) > float(m.group(1)):
            return -1
    if ctx.get("custom_long"):
        return 1
    if ctx.get("custom_short"):
        return -1
    return 0


def build_signals(
    config: StrategyConfig,
    primary: pd.DataFrame,
    context_frames: dict[str, pd.DataFrame],
    context_idx: dict[str, pd.Series],
) -> pd.Series:
    if config.mode == "preset":
        return preset_signals(config.preset or "trend_ema_cross", primary)

    ind_series: dict[str, pd.Series] = {}
    for spec in config.custom_indicators:
        name = spec.get("name", "RSI")
        tf = spec.get("timeframe", "primary")
        params = spec.get("params", {})
        df = primary if tf == "primary" else context_frames.get(tf, primary)
        series = compute_indicator(name, df, params)
        if tf != "primary":
            aligned = series.iloc[context_idx[tf].clip(lower=0).values].reset_index(drop=True)
            ind_series[f"{tf}_{name}"] = aligned
        else:
            ind_series[f"primary_{name}"] = series.reset_index(drop=True)

    signals = []
    rule = config.custom_rule or "flat"
    for i in range(len(primary)):
        ctx: dict[str, float] = {}
        for k, s in ind_series.items():
            if i < len(s) and pd.notna(s.iloc[i]):
                ctx[k.upper()] = float(s.iloc[i])
                if k.upper() == "PRIMARY_RSI":
                    ctx["primary_RSI"] = float(s.iloc[i])
        # EMA filter example on 4h
        if "4h" in context_frames and "4h" in context_idx:
            j = int(context_idx["4h"].iloc[i])
            if j >= 0:
                c4 = context_frames["4h"]["close"].iloc[j]
                e4 = ema(context_frames["4h"]["close"], 200).iloc[j]
                ctx["custom_long"] = c4 > e4 and ctx.get("primary_RSI", 50) < 35
                ctx["custom_short"] = c4 < e4 and ctx.get("primary_RSI", 50) > 65
        signals.append(_eval_simple_rule(rule, ctx))
    return pd.Series(signals, index=primary.index)
