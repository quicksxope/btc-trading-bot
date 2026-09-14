"""USD prop rules (Phase B): daily loss, static/trailing max loss, consistency."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from engine.models import PropFirmConfig
from engine.prop.firm import PropState, load_prop_pack


@dataclass
class PropUsdSpec:
    pack_id: str
    initial_balance_usd: float
    daily_loss_limit_usd: float
    max_loss_limit_usd: float
    max_loss_mode: Literal["static", "trailing_eod"] = "static"
    mll_lock_at_initial: bool = False
    profit_target_usd: float | None = None
    min_trading_days: int | None = None
    consistency_pct: float | None = None
    consistency_rule: Literal["hola_best_day", "topstep_target_ratio", "none"] = "none"
    consistency_target_ratio: float = 0.5


def pack_uses_usd_engine(pack_id: str) -> bool:
    return load_prop_pack(pack_id).engine == "usd"


def resolve_usd_spec(prop: PropFirmConfig, initial_balance: float) -> PropUsdSpec | None:
    pack = load_prop_pack(prop.pack_id)
    if pack.engine != "usd":
        return None
    ref = pack.reference_usd or {}
    initial = float(pack.initial_balance_usd or initial_balance)

    def usd(key: str, fallback: float | None = None) -> float | None:
        if pack.usd_rules and pack.usd_rules.get(key) is not None:
            return float(pack.usd_rules[key])
        if ref.get(key) is not None:
            return float(ref[key])
        if key == "max_loss" and ref.get("max_loss") is not None:
            return float(ref["max_loss"])
        if key == "daily_loss" and ref.get("daily_loss") is not None:
            return float(ref["daily_loss"])
        if key == "profit_target" and ref.get("profit_target") is not None:
            return float(ref["profit_target"])
        return fallback

    daily = usd("daily_loss_limit_usd") or usd("daily_loss")
    max_loss = usd("max_loss_limit_usd") or usd("max_loss")
    if daily is None or max_loss is None:
        daily = daily or initial * (prop.daily_loss_pct / 100)
        max_loss = max_loss or initial * (prop.max_drawdown_pct / 100)

    pt = usd("profit_target_usd") or usd("profit_target")
    rules = pack.usd_rules or {}
    return PropUsdSpec(
        pack_id=prop.pack_id,
        initial_balance_usd=initial,
        daily_loss_limit_usd=float(daily),
        max_loss_limit_usd=float(max_loss),
        max_loss_mode=pack.max_loss_mode,
        mll_lock_at_initial=pack.mll_lock_at_initial,
        profit_target_usd=float(pt) if pt is not None else None,
        min_trading_days=prop.min_trading_days if prop.min_trading_days is not None else pack.min_trading_days,
        consistency_pct=pack.consistency_pct,
        consistency_rule=pack.consistency_rule,
        consistency_target_ratio=pack.consistency_target_ratio,
    )


def max_loss_floor(
    spec: PropUsdSpec,
    eod_peak: float,
) -> float:
    if spec.max_loss_mode == "static":
        return spec.initial_balance_usd - spec.max_loss_limit_usd
    floor = eod_peak - spec.max_loss_limit_usd
    if spec.mll_lock_at_initial and floor >= spec.initial_balance_usd:
        return spec.initial_balance_usd
    return floor


def _trading_days_from_trades(trades_df: pd.DataFrame) -> int:
    if trades_df is None or trades_df.empty or "exit_time" not in trades_df.columns:
        return 0
    days = pd.to_datetime(trades_df["exit_time"]).dt.date
    return int(days.nunique())


def _daily_pnl_usd(trades_df: pd.DataFrame) -> pd.Series:
    if trades_df is None or trades_df.empty:
        return pd.Series(dtype=float)
    t = trades_df.copy()
    t["exit_time"] = pd.to_datetime(t["exit_time"])
    t["day"] = t["exit_time"].dt.date
    return t.groupby("day")["pnl"].sum()


def check_consistency_hola(daily_pnl: pd.Series, limit_pct: float) -> tuple[bool, str]:
    total = float(daily_pnl.sum())
    if total <= 0:
        return True, "consistency N/A (non-positive cycle profit)"
    best = float(daily_pnl.max())
    best_pct = best / total * 100
    if best_pct <= limit_pct:
        return True, f"consistency PASS (best day {best_pct:.1f}% of profit, limit {limit_pct:g}%)"
    need = best / (limit_pct / 100)
    return (
        False,
        f"consistency FAIL (best day {best_pct:.1f}% > {limit_pct:g}%; need total ${need:,.0f})",
    )


def check_consistency_topstep(daily_pnl: pd.Series, profit_target: float, ratio: float) -> tuple[bool, str]:
    cap = profit_target * ratio
    if daily_pnl.empty:
        return True, "consistency N/A (no trades)"
    best = float(daily_pnl.max())
    if best <= cap:
        return True, f"consistency PASS (best day ${best:,.0f} ≤ ${cap:,.0f})"
    return False, f"consistency FAIL (best day ${best:,.0f} > ${cap:,.0f} cap)"


def evaluate_equity_usd_breaches(
    equity_df: pd.DataFrame,
    spec: PropUsdSpec,
) -> tuple[bool, str | None, float]:
    """Scan bar equity for daily USD loss and max-loss floor breaches."""
    if equity_df.empty:
        return True, None, 0.0

    initial = spec.initial_balance_usd
    eod_peak = initial
    prev_day = None
    day_start = initial
    worst_daily_usd = 0.0
    prev_close = initial

    for row in equity_df.itertuples():
        ts = row.timestamp
        mark = float(row.equity)
        day = ts.date() if hasattr(ts, "date") else pd.Timestamp(ts).date()

        if prev_day is not None and day != prev_day:
            eod_peak = max(eod_peak, prev_close)
            day_start = mark
        elif prev_day is None:
            day_start = initial

        floor = max_loss_floor(spec, eod_peak)
        if mark <= floor:
            return False, f"MAX_LOSS floor ${floor:,.0f} breached (eq ${mark:,.0f})", worst_daily_usd

        daily_loss = day_start - mark
        if daily_loss > worst_daily_usd:
            worst_daily_usd = daily_loss
        if daily_loss > spec.daily_loss_limit_usd:
            return (
                False,
                f"DAILY_LOSS ${daily_loss:,.0f} > ${spec.daily_loss_limit_usd:,.0f} on {day}",
                worst_daily_usd,
            )

        prev_day = day
        prev_close = mark

    eod_peak = max(eod_peak, prev_close if equity_df.shape[0] else initial)
    return True, None, worst_daily_usd


def evaluate_prop_usd(
    prop: PropFirmConfig,
    equity_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    initial: float,
) -> PropState:
    spec = resolve_usd_spec(prop, initial)
    if spec is None:
        return PropState(pass_prop=True)

    ok, breach, worst_daily_usd = evaluate_equity_usd_breaches(equity_df, spec)
    trading_days = _trading_days_from_trades(trades_df)
    final_eq = float(equity_df["equity"].iloc[-1]) if not equity_df.empty else initial
    net_profit = final_eq - spec.initial_balance_usd
    worst_daily_pct = (worst_daily_usd / spec.initial_balance_usd * 100) if spec.initial_balance_usd else 0

    details: list[str] = []
    if not ok:
        return PropState(
            pass_prop=False,
            fail_reason=breach,
            worst_daily_loss_pct=worst_daily_pct,
            trading_days=trading_days,
            detail=breach,
        )

    if spec.profit_target_usd is not None:
        if net_profit < spec.profit_target_usd:
            return PropState(
                pass_prop=False,
                fail_reason=f"PROFIT_TARGET ${net_profit:,.0f} < ${spec.profit_target_usd:,.0f}",
                worst_daily_loss_pct=worst_daily_pct,
                trading_days=trading_days,
            )
        details.append(f"target met ${net_profit:,.0f} / ${spec.profit_target_usd:,.0f}")

    if spec.min_trading_days and trading_days < spec.min_trading_days:
        return PropState(
            pass_prop=False,
            fail_reason=f"MIN_DAYS {trading_days} < {spec.min_trading_days}",
            worst_daily_loss_pct=worst_daily_pct,
            trading_days=trading_days,
        )

    daily_pnl = _daily_pnl_usd(trades_df)
    if spec.consistency_rule == "hola_best_day" and spec.consistency_pct:
        c_ok, c_msg = check_consistency_hola(daily_pnl, spec.consistency_pct)
        details.append(c_msg)
        if not c_ok:
            return PropState(
                pass_prop=False,
                fail_reason=c_msg,
                worst_daily_loss_pct=worst_daily_pct,
                trading_days=trading_days,
                detail="; ".join(details),
            )
    elif spec.consistency_rule == "topstep_target_ratio" and spec.profit_target_usd:
        c_ok, c_msg = check_consistency_topstep(
            daily_pnl, spec.profit_target_usd, spec.consistency_target_ratio
        )
        details.append(c_msg)
        if not c_ok:
            return PropState(
                pass_prop=False,
                fail_reason=c_msg,
                worst_daily_loss_pct=worst_daily_pct,
                trading_days=trading_days,
                detail="; ".join(details),
            )

    return PropState(
        pass_prop=True,
        worst_daily_loss_pct=worst_daily_pct,
        trading_days=trading_days,
        detail="; ".join(details) if details else "USD rules PASS",
    )


@dataclass
class UsdBarGate:
    """Intrabar halt flags for backtest loop."""

    account_halted: bool = False
    daily_blocked: bool = False
    eod_peak: float = 0.0
    day_start_equity: float = 0.0
    current_day: str | None = None

    def on_new_day(self, day_key: str, mark: float) -> None:
        if self.current_day is not None:
            self.eod_peak = max(self.eod_peak, mark)
        self.current_day = day_key
        self.day_start_equity = mark
        self.daily_blocked = False

    def check(
        self,
        spec: PropUsdSpec,
        mark: float,
    ) -> str | None:
        if self.account_halted:
            return "halted"
        floor = max_loss_floor(spec, self.eod_peak)
        if mark <= floor:
            self.account_halted = True
            return f"MAX_LOSS floor ${floor:,.0f}"
        if mark <= self.day_start_equity - spec.daily_loss_limit_usd:
            self.daily_blocked = True
            return f"DAILY_LOSS ${spec.daily_loss_limit_usd:,.0f}"
        return None

    def can_enter(self) -> bool:
        return not self.account_halted and not self.daily_blocked
