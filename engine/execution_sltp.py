"""SL/TP + USD risk sizing (Hola-style execution)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from engine.models import ExecutionConfig
from engine.prop_firm import load_prop_pack


@dataclass
class OpenTrade:
    direction: int
    entry_price: float
    size_units: float
    stop_loss: float
    take_profit: float
    entry_time: datetime


def enrich_execution_from_pack(execution: ExecutionConfig, pack_id: str | None) -> ExecutionConfig:
    if not pack_id or pack_id in ("none", "generic"):
        return execution
    pack = load_prop_pack(pack_id)
    defaults = pack.execution_defaults or {}
    if not defaults:
        return execution
    data = execution.model_dump()
    for key, val in defaults.items():
        if key not in ExecutionConfig.model_fields:
            continue
        if key == "mode" and execution.mode != "signal_flip":
            continue
        if key == "risk_per_trade_usd" and execution.risk_per_trade_usd is not None:
            continue
        data[key] = val
    return ExecutionConfig(**data)


def swing_stops_long(
    lows: pd.Series,
    end_idx: int,
    entry_price: float,
    lookback: int,
    rr: float,
) -> tuple[float, float, float] | None:
    start = max(0, end_idx - lookback + 1)
    sl = float(lows.iloc[start : end_idx + 1].min())
    risk = entry_price - sl
    if not (risk > 0 and pd.notna(risk)):
        return None
    tp = entry_price + risk * rr
    return sl, tp, risk


def swing_stops_short(
    highs: pd.Series,
    end_idx: int,
    entry_price: float,
    lookback: int,
    rr: float,
) -> tuple[float, float, float] | None:
    start = max(0, end_idx - lookback + 1)
    sl = float(highs.iloc[start : end_idx + 1].max())
    risk = sl - entry_price
    if not (risk > 0 and pd.notna(risk)):
        return None
    tp = entry_price - risk * rr
    return sl, tp, risk


def size_units_for_risk(
    risk_usd: float,
    risk_distance: float,
    contract_size: float,
    equity: float,
    max_equity_fraction: float,
) -> float:
    if risk_distance <= 0 or contract_size <= 0 or equity <= 0 or risk_usd <= 0:
        return 0.0
    raw = risk_usd / (risk_distance * contract_size)
    cap = (equity * max_equity_fraction) / max(risk_distance * contract_size, 1e-12)
    return max(0.0, min(raw, cap))


def risk_budget_usd(
    risk_per_trade: float,
    day_start_equity: float,
    equity: float,
    daily_loss_limit_usd: float | None,
) -> float:
    if daily_loss_limit_usd is None or daily_loss_limit_usd <= 0:
        return risk_per_trade
    floor = day_start_equity - daily_loss_limit_usd
    remaining = equity - floor
    return max(0.0, min(risk_per_trade, remaining))


def intrabar_exit(trade: OpenTrade, high: float, low: float) -> tuple[float, str] | None:
    """Return (exit_price, reason). SL assumed first if both touched."""
    if trade.direction > 0:
        if low <= trade.stop_loss:
            return trade.stop_loss, "sl"
        if high >= trade.take_profit:
            return trade.take_profit, "tp"
    else:
        if high >= trade.stop_loss:
            return trade.stop_loss, "sl"
        if low <= trade.take_profit:
            return trade.take_profit, "tp"
    return None


def close_trade_pnl(
    trade: OpenTrade,
    exit_price: float,
    contract_size: float,
    spread_points: float,
    point_value: float,
) -> float:
    pnl = (exit_price - trade.entry_price) * trade.direction * trade.size_units * contract_size
    if spread_points:
        pnl -= spread_points * point_value
    return pnl
