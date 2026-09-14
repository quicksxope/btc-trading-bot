"""Event-driven bar backtest core."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import pandas as pd

from engine.data_loader import load_bars
from engine.instruments import load_instrument_profile
from engine.models import BacktestConfig, BacktestResult, InstrumentProfile
from engine.mtf import align_context_to_primary, resample_bars
from engine.prop_firm import PropState, evaluate_prop_backtest, load_prop_pack, merge_prop_config
from engine.prop_usd import UsdBarGate, resolve_usd_spec
from engine.session import is_in_session, session_day_key
from engine.strategy import build_signals

TF_RULES = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1D",
}


ProgressCallback = Callable[[str, float], None]


def _day_key(ts: datetime, config: BacktestConfig) -> str:
    if config.execution.daily_reset == "utc":
        return ts.strftime("%Y-%m-%d")
    if config.session.use_for_accounting:
        return session_day_key(ts, config.session.id)
    return ts.strftime("%Y-%m-%d")


def run_backtest(
    config: BacktestConfig,
    on_progress: ProgressCallback | None = None,
    *,
    skip_ensure: bool = False,
) -> tuple[BacktestResult, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    def prog(stage: str, pct: float) -> None:
        if on_progress:
            on_progress(stage, pct)

    if not skip_ensure:
        from engine.data_ensure import ensure_bars_for_config

        ensure_bars_for_config(config, on_progress=prog)

    prog("Loading data", 35)
    profile = load_instrument_profile(config.instrument)
    prop = merge_prop_config(config.prop_firm)

    primary_tf = config.timeframes.primary
    primary = load_bars(
        profile.data_symbol,
        primary_tf,
        config.date_range.start,
        config.date_range.end,
    )

    prog("Building MTF", 45)
    context_frames: dict[str, pd.DataFrame] = {}
    context_idx: dict[str, pd.Series] = {}
    base = load_bars(
        profile.data_symbol,
        "1h",
        config.date_range.start,
        config.date_range.end,
    )
    for tf in config.timeframes.context:
        rule = TF_RULES.get(tf, tf)
        if tf == primary_tf:
            context_frames[tf] = primary
        else:
            try:
                context_frames[tf] = load_bars(
                    profile.data_symbol, tf, config.date_range.start, config.date_range.end
                )
            except FileNotFoundError:
                context_frames[tf] = resample_bars(base, rule)
        context_idx[tf] = align_context_to_primary(primary, context_frames[tf])

    signals = build_signals(config.strategy, primary, context_frames, context_idx)

    balance = config.execution.initial_balance
    equity = balance
    position = 0.0
    entry_price = 0.0
    peak = balance
    max_dd = 0.0

    trades: list[dict] = []
    equity_rows: list[dict] = []
    daily_pnl_pct: dict[str, float] = {}
    day_start_equity: dict[str, float] = {}
    breach_log: list[str] = []
    usd_spec = resolve_usd_spec(prop, config.execution.initial_balance) if prop.enabled else None
    usd_gate = UsdBarGate(eod_peak=config.execution.initial_balance)
    usd_gate.day_start_equity = config.execution.initial_balance
    last_dk: str | None = None
    prev_mark = config.execution.initial_balance

    n = len(primary)
    prog("Simulating", 50)

    for i in range(n):
        if i > 0 and i % max(1, n // 10) == 0:
            prog("Simulating", 50 + (i / n) * 35)

        row = primary.iloc[i]
        ts = row["timestamp"].to_pydatetime()
        dk = _day_key(ts, config)
        if last_dk is not None and dk != last_dk:
            usd_gate.eod_peak = max(usd_gate.eod_peak, prev_mark)
            usd_gate.day_start_equity = equity
            usd_gate.daily_blocked = False
        if dk not in day_start_equity:
            day_start_equity[dk] = equity
        last_dk = dk

        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
        fill_price = o if config.execution.fill == "next_bar_open" and i > 0 else c

        if profile.asset_class.value == "crypto_perp" and position != 0 and i % 8 == 0:
            funding = position * c * profile.contract_size * (profile.funding_bps_per_8h / 10000)
            equity -= funding

        sig = int(signals.iloc[i - 1]) if i > 0 else 0
        if i == 0:
            sig = 0

        can_enter = is_in_session(ts, config.session.id) if config.session.use_for_trading else True
        if config.session.id.value != "all_day" and config.session.use_for_trading:
            can_enter = can_enter
        elif config.session.id.value == "all_day":
            can_enter = True

        target_dir = sig
        if not can_enter and position == 0:
            target_dir = 0

        can_enter_usd = usd_gate.can_enter() if usd_spec else True

        if i > 0:
            if position == 0 and target_dir != 0 and can_enter and can_enter_usd:
                position = target_dir
                entry_price = fill_price
                fee = abs(c * profile.contract_size * profile.fee_bps / 10000)
                equity -= fee
            elif position != 0 and target_dir != position:
                pnl = (fill_price - entry_price) * position * profile.contract_size
                if profile.spread_points:
                    pnl -= profile.spread_points * profile.point_value
                equity += pnl
                fee = abs(fill_price * profile.contract_size * profile.fee_bps / 10000)
                equity -= fee
                trades.append(
                    {
                        "exit_time": ts,
                        "pnl": pnl - fee,
                        "side": "long" if position > 0 else "short",
                    }
                )
                position = (
                    target_dir if (target_dir != 0 and can_enter and can_enter_usd) else 0
                )
                if position != 0:
                    entry_price = fill_price

        if position != 0:
            unrealized = (c - entry_price) * position * profile.contract_size
            mark = equity + unrealized
        else:
            mark = equity

        peak = max(peak, mark)
        dd = (peak - mark) / peak * 100 if peak else 0
        max_dd = max(max_dd, dd)

        daily_pnl_pct[dk] = (mark - day_start_equity[dk]) / day_start_equity[dk] * 100

        if usd_spec:
            breach = usd_gate.check(usd_spec, mark)
            if breach:
                msg = f"{ts} {breach}"
                if not breach_log or breach_log[-1] != msg:
                    breach_log.append(msg)

        if prop.enabled and not usd_spec:
            if daily_pnl_pct[dk] < -prop.daily_loss_pct:
                breach_log.append(f"{dk} DAILY_LOSS {daily_pnl_pct[dk]:.2f}%")
            if dd > prop.max_drawdown_pct:
                breach_log.append(f"{ts} MAX_DD {dd:.2f}%")

        equity_rows.append({"timestamp": ts, "equity": mark, "drawdown_pct": dd})
        prev_mark = mark

    if position != 0:
        last = primary.iloc[-1]
        c = float(last["close"])
        pnl = (c - entry_price) * position * profile.contract_size
        equity += pnl
        trades.append(
            {
                "exit_time": last["timestamp"],
                "pnl": pnl,
                "side": "long" if position > 0 else "short",
            }
        )

    equity_final = equity
    net_pnl_pct = (equity_final - config.execution.initial_balance) / config.execution.initial_balance * 100

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0.0
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    profit_factor = gross_win / gross_loss if gross_loss else float("inf")

    prog("Prop evaluation", 90)
    eq_list = [r["equity"] for r in equity_rows]
    equity_df = pd.DataFrame(equity_rows)
    prop_state: PropState = evaluate_prop_backtest(
        prop,
        daily_pnl_pct,
        eq_list,
        equity_df,
        pd.DataFrame(trades),
        config.execution.initial_balance,
    )
    pack_meta = load_prop_pack(prop.pack_id)

    result = BacktestResult(
        net_pnl_pct=net_pnl_pct,
        max_drawdown_pct=max_dd,
        win_rate=win_rate,
        trade_count=len(trades),
        profit_factor=min(profit_factor, 99.0),
        prop_pass=prop_state.pass_prop,
        prop_fail_reason=prop_state.fail_reason,
        prop_detail=prop_state.detail,
        prop_engine=pack_meta.engine if prop.enabled else "off",
        worst_daily_loss_pct=prop_state.worst_daily_loss_pct,
        trading_days=prop_state.trading_days,
        equity_final=equity_final,
    )

    trades_df = pd.DataFrame(trades)
    daily_df = pd.DataFrame(
        [{"day": k, "pnl_pct": v} for k, v in sorted(daily_pnl_pct.items())]
    )
    prog("Done", 100)
    return result, equity_df, trades_df, daily_df, breach_log
