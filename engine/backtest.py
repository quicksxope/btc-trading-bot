"""Event-driven bar backtest core."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import pandas as pd

from engine.data_loader import load_bars
from engine.instruments import load_instrument_profile
from engine.models import BacktestConfig, BacktestResult, InstrumentProfile
from engine.mtf import align_context_to_primary, resample_bars
from engine.execution_sltp import (
    OpenTrade,
    close_trade_pnl,
    enrich_execution_from_pack,
    intrabar_exit,
    risk_budget_usd,
    capped_risk_per_trade_usd,
    size_units_for_risk,
    swing_stops_long,
    swing_stops_short,
)
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


def load_backtest_frames(
    config: BacktestConfig,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict[str, pd.Series], InstrumentProfile]:
    profile = load_instrument_profile(config.instrument)
    primary_tf = config.timeframes.primary
    primary = load_bars(
        profile.data_symbol,
        primary_tf,
        config.date_range.start,
        config.date_range.end,
    )
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
    return primary, context_frames, context_idx, profile


def simulate_backtest(
    config: BacktestConfig,
    primary: pd.DataFrame,
    context_frames: dict[str, pd.DataFrame],
    context_idx: dict[str, pd.Series],
    profile: InstrumentProfile,
    on_progress: ProgressCallback | None = None,
) -> tuple[BacktestResult, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    def prog(stage: str, pct: float) -> None:
        if on_progress:
            on_progress(stage, pct)

    prop = merge_prop_config(config.prop_firm)
    signals = build_signals(config.strategy, primary, context_frames, context_idx)

    exec_cfg = enrich_execution_from_pack(
        config.execution,
        prop.pack_id if prop.enabled else None,
    )
    use_sltp = exec_cfg.mode == "sltp_risk" and exec_cfg.risk_per_trade_usd is not None

    balance = config.execution.initial_balance
    equity = balance
    position = 0.0
    entry_price = 0.0
    open_trade: OpenTrade | None = None
    trades_today: dict[str, int] = {}
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

        in_position = open_trade is not None if use_sltp else position != 0
        if profile.asset_class.value == "crypto_perp" and in_position and i % 8 == 0:
            if use_sltp and open_trade:
                notional = open_trade.size_units * c * profile.contract_size
                funding = open_trade.direction * notional * (profile.funding_bps_per_8h / 10000)
            else:
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
        if not can_enter and not in_position:
            target_dir = 0

        can_enter_usd = usd_gate.can_enter() if usd_spec else True

        if use_sltp and i > 0 and open_trade is not None:
            hit = intrabar_exit(open_trade, h, l)
            if hit:
                exit_price, reason = hit
                pnl = close_trade_pnl(
                    open_trade,
                    exit_price,
                    profile.contract_size,
                    profile.spread_points,
                    profile.point_value,
                )
                fee = abs(
                    exit_price * open_trade.size_units * profile.contract_size * profile.fee_bps / 10000
                )
                equity += pnl - fee
                risk_usd = abs(open_trade.entry_price - open_trade.stop_loss) * open_trade.size_units * profile.contract_size
                trades.append(
                    {
                        "exit_time": ts,
                        "pnl": pnl - fee,
                        "side": "long" if open_trade.direction > 0 else "short",
                        "exit_reason": reason,
                        "r_multiple": (pnl - fee) / risk_usd if risk_usd else 0.0,
                    }
                )
                open_trade = None

        if use_sltp:
            if i > 0 and open_trade is None and target_dir != 0 and can_enter and can_enter_usd:
                max_td = exec_cfg.max_trades_per_day
                if max_td is not None and trades_today.get(dk, 0) >= max_td:
                    target_dir = 0
                if target_dir != 0:
                    signal_bar = i - 1
                    entry_px = fill_price
                    if target_dir > 0:
                        stops = swing_stops_long(
                            primary["low"],
                            signal_bar,
                            entry_px,
                            exec_cfg.swing_lookback,
                            exec_cfg.risk_reward_ratio,
                        )
                    else:
                        stops = swing_stops_short(
                            primary["high"],
                            signal_bar,
                            entry_px,
                            exec_cfg.swing_lookback,
                            exec_cfg.risk_reward_ratio,
                        )
                    if stops:
                        sl, tp, risk_dist = stops
                        daily_cap = usd_spec.daily_loss_limit_usd if usd_spec else None
                        base_risk = exec_cfg.risk_per_trade_usd or 0.0
                        if prop.enabled:
                            base_risk = capped_risk_per_trade_usd(
                                base_risk,
                                prop,
                                config.execution.initial_balance,
                            )
                        budget = risk_budget_usd(
                            base_risk,
                            usd_gate.day_start_equity,
                            equity,
                            daily_cap,
                        )
                        size_u = size_units_for_risk(
                            budget,
                            risk_dist,
                            profile.contract_size,
                            equity,
                            exec_cfg.max_equity_fraction,
                        )
                        if size_u > 0:
                            fee = abs(
                                entry_px * size_u * profile.contract_size * profile.fee_bps / 10000
                            )
                            equity -= fee
                            open_trade = OpenTrade(
                                direction=target_dir,
                                entry_price=entry_px,
                                size_units=size_u,
                                stop_loss=sl,
                                take_profit=tp,
                                entry_time=ts,
                            )
                            trades_today[dk] = trades_today.get(dk, 0) + 1
        elif i > 0:
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

        if use_sltp and open_trade is not None:
            unrealized = (
                (c - open_trade.entry_price)
                * open_trade.direction
                * open_trade.size_units
                * profile.contract_size
            )
            mark = equity + unrealized
        elif not use_sltp and position != 0:
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

    if use_sltp and open_trade is not None and exec_cfg.finalize_open_at_end:
        last = primary.iloc[-1]
        c = float(last["close"])
        pnl = close_trade_pnl(
            open_trade,
            c,
            profile.contract_size,
            profile.spread_points,
            profile.point_value,
        )
        equity += pnl
        trades.append(
            {
                "exit_time": last["timestamp"],
                "pnl": pnl,
                "side": "long" if open_trade.direction > 0 else "short",
                "exit_reason": "finalize",
            }
        )
    elif not use_sltp and position != 0:
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
        wins=len(wins),
        losses=len(losses),
        profit_factor=min(profit_factor, 99.0),
        prop_pass=prop_state.pass_prop,
        prop_fail_reason=prop_state.fail_reason,
        prop_detail=prop_state.detail,
        prop_engine=pack_meta.engine if prop.enabled else "off",
        worst_daily_loss_pct=prop_state.worst_daily_loss_pct,
        trading_days=prop_state.trading_days,
        equity_final=equity_final,
        execution_mode=exec_cfg.mode if use_sltp else "signal_flip",
    )

    trades_df = pd.DataFrame(trades)
    daily_df = pd.DataFrame(
        [{"day": k, "pnl_pct": v} for k, v in sorted(daily_pnl_pct.items())]
    )
    prog("Done", 100)
    return result, equity_df, trades_df, daily_df, breach_log


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
    primary, context_frames, context_idx, profile = load_backtest_frames(config)
    prog("Building MTF", 45)
    return simulate_backtest(
        config, primary, context_frames, context_idx, profile, on_progress=on_progress
    )
