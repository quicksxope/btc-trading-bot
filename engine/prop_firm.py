"""Prop firm rule packs and simulation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from engine.models import InstrumentId, PropFirmConfig

ROOT = Path(__file__).resolve().parents[1]
PACKS_DIR = ROOT / "configs" / "prop_firms"


@dataclass
class PropPack:
    pack_id: str
    daily_loss_pct: float
    max_drawdown_pct: float
    profit_target_pct: float | None
    min_trading_days: int | None
    allowed_instruments: list[str]
    description: str = ""
    label: str = ""
    initial_balance_usd: float | None = None
    reference_usd: dict | None = None
    engine: str = "pct"
    max_loss_mode: str = "static"
    mll_lock_at_initial: bool = False
    consistency_pct: float | None = None
    consistency_rule: str = "none"
    consistency_target_ratio: float = 0.5
    usd_rules: dict | None = None


def load_prop_pack(pack_id: str) -> PropPack:
    path = PACKS_DIR / f"{pack_id}.yaml"
    if path.exists():
        raw = yaml.safe_load(path.read_text()) or {}
        return PropPack(
            pack_id=pack_id,
            daily_loss_pct=raw.get("daily_loss_pct", 5),
            max_drawdown_pct=raw.get("max_drawdown_pct", 10),
            profit_target_pct=raw.get("profit_target_pct"),
            min_trading_days=raw.get("min_trading_days"),
            allowed_instruments=raw.get("allowed_instruments", []),
            description=raw.get("description", ""),
            label=raw.get("label") or pack_id,
            initial_balance_usd=raw.get("initial_balance_usd"),
            reference_usd=raw.get("reference_usd"),
            engine=str(raw.get("engine", "pct")),
            max_loss_mode=str(raw.get("max_loss_mode", "static")),
            mll_lock_at_initial=bool(raw.get("mll_lock_at_initial", False)),
            consistency_pct=raw.get("consistency_pct"),
            consistency_rule=str(raw.get("consistency_rule", "none")),
            consistency_target_ratio=float(raw.get("consistency_target_ratio", 0.5)),
            usd_rules=raw.get("usd_rules"),
        )
    return PropPack(
        pack_id=pack_id,
        daily_loss_pct=5,
        max_drawdown_pct=10,
        profit_target_pct=None,
        min_trading_days=None,
        allowed_instruments=[],
    )


def merge_prop_config(config: PropFirmConfig) -> PropFirmConfig:
    """Template pack defaults merged with user overrides on config."""
    if not config.enabled:
        return config
    pack = load_prop_pack(config.pack_id)

    def pick(user_val, pack_val):
        if config.pack_id == "generic":
            return user_val
        return user_val if user_val is not None else pack_val

    return PropFirmConfig(
        enabled=True,
        pack_id=config.pack_id,
        daily_loss_pct=float(pick(config.daily_loss_pct, pack.daily_loss_pct)),
        max_drawdown_pct=float(pick(config.max_drawdown_pct, pack.max_drawdown_pct)),
        profit_target_pct=pick(config.profit_target_pct, pack.profit_target_pct),
        min_trading_days=pick(config.min_trading_days, pack.min_trading_days),
    )


def instrument_allowed(pack_id: str, instrument: InstrumentId) -> tuple[bool, str]:
    pack = load_prop_pack(pack_id)
    if not pack.allowed_instruments:
        return True, ""
    if instrument.value in pack.allowed_instruments:
        return True, ""
    return False, f"{instrument.value} not in {pack.allowed_instruments}"


@dataclass
class PropState:
    pass_prop: bool = True
    fail_reason: str | None = None
    worst_daily_loss_pct: float = 0.0
    trading_days: int = 0
    detail: str | None = None


def evaluate_prop_backtest(
    prop: PropFirmConfig,
    daily_pnl_pct: dict[str, float],
    equity_curve: list[float],
    equity_df,
    trades_df,
    initial: float,
) -> PropState:
    """Pct engine or USD Phase B depending on pack template."""
    if not prop.enabled:
        return PropState(pass_prop=True, trading_days=len(daily_pnl_pct))
    pack = load_prop_pack(prop.pack_id)
    if pack.engine == "usd":
        from engine.prop_usd import evaluate_prop_usd

        return evaluate_prop_usd(prop, equity_df, trades_df, initial)
    return evaluate_prop(daily_pnl_pct, equity_curve, initial, prop)


def evaluate_prop(
    daily_pnl_pct: dict[str, float],
    equity_curve: list[float],
    initial: float,
    prop: PropFirmConfig,
) -> PropState:
    if not prop.enabled:
        return PropState(pass_prop=True, trading_days=len(daily_pnl_pct))

    state = PropState(trading_days=len(daily_pnl_pct))
    peak = initial
    max_dd = 0.0
    for eq in equity_curve:
        peak = max(peak, eq)
        dd = (peak - eq) / peak * 100 if peak else 0
        max_dd = max(max_dd, dd)

    worst_daily = min(daily_pnl_pct.values()) if daily_pnl_pct else 0.0
    state.worst_daily_loss_pct = abs(min(0, worst_daily))

    if max_dd > prop.max_drawdown_pct:
        state.pass_prop = False
        state.fail_reason = f"MAX_DD {max_dd:.2f}% > {prop.max_drawdown_pct}%"
        return state

    if state.worst_daily_loss_pct > prop.daily_loss_pct:
        state.pass_prop = False
        state.fail_reason = (
            f"DAILY_LOSS {state.worst_daily_loss_pct:.2f}% > {prop.daily_loss_pct}%"
        )
        return state

    if prop.profit_target_pct is not None:
        final = equity_curve[-1] if equity_curve else initial
        ret = (final - initial) / initial * 100
        if ret < prop.profit_target_pct:
            state.pass_prop = False
            state.fail_reason = f"PROFIT_TARGET not met ({ret:.2f}%)"
            return state

    if prop.min_trading_days and state.trading_days < prop.min_trading_days:
        state.pass_prop = False
        state.fail_reason = f"MIN_DAYS {state.trading_days} < {prop.min_trading_days}"
        return state

    return state
