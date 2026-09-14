"""Telegram text for indicator study results."""

from __future__ import annotations

from html import escape

from engine.models import BacktestResult


def _pnl_trades(br: BacktestResult, *, pnl_decimals: int = 2) -> str:
    base = f"{br.net_pnl_pct:+.{pnl_decimals}f}% · {br.trade_count} trades"
    if br.trade_count:
        if br.wins + br.losses == br.trade_count:
            base += f" ({br.wins}W/{br.losses}L"
        else:
            est_w = int(round(br.trade_count * br.win_rate / 100))
            base += f" (~{est_w}W/{br.trade_count - est_w}L"
        base += f" · WR {br.win_rate:.0f}%)"
    if br.trade_count and br.trading_days:
        base += f" · {br.trading_days}d w/ exits"
    return base


def _signal_hint(row: dict) -> str:
    lo = row.get("signal_bars_long")
    sh = row.get("signal_bars_short")
    if lo is None and sh is None:
        return ""
    return f" · sig L{lo}/S{sh} bars"


def _prop_summary_line(prop_pack_id: str | None) -> str | None:
    if not prop_pack_id:
        return None
    from engine.execution_sltp import capped_risk_per_trade_usd
    from engine.models import PropFirmConfig
    from engine.prop_firm import load_prop_pack

    pack = load_prop_pack(prop_pack_id)
    ref = pack.reference_usd or {}
    ex = pack.execution_defaults or {}
    tpl_risk = float(ref.get("risk_per_trade") or ex.get("risk_per_trade_usd") or 0)
    prop_cfg = PropFirmConfig(
        enabled=True,
        pack_id=prop_pack_id,
        daily_loss_pct=pack.daily_loss_pct,
        max_drawdown_pct=pack.max_drawdown_pct,
    )
    eff = capped_risk_per_trade_usd(tpl_risk, prop_cfg, float(pack.initial_balance_usd or 50_000))
    bits = [escape(pack.label or prop_pack_id)]
    if ref.get("daily_loss") is not None:
        bits.append(f"DLL ${ref['daily_loss']:,.0f}")
    if ref.get("max_loss") is not None:
        bits.append(f"MLL ${ref['max_loss']:,.0f}")
    if tpl_risk:
        risk_s = f"risk/trade ≤ ${eff:,.0f}"
        if eff + 1e-6 < tpl_risk:
            risk_s += f" (tpl ${tpl_risk:,.0f})"
        bits.append(risk_s)
    return "Prop: " + " · ".join(bits)


def study_result_summary(
    job_id: str,
    payload: dict,
    instrument: str,
    primary_tf: str,
    *,
    prop_pack_id: str | None = None,
) -> str:
    rows = payload.get("rows") or []
    pool = payload.get("indicator_pool") or []
    mix_count = payload.get("mix_count") or len(rows)
    pass_count = payload.get("pass_count") or 0
    best_label = payload.get("best_mix_label") or "—"
    best = payload.get("best")

    lines = [
        f"<b>Indicator study</b> <code>{escape(job_id)}</code>",
        f"{escape(instrument)} · {escape(primary_tf)} · pool: {escape('+'.join(pool))}",
    ]
    prop_line = _prop_summary_line(prop_pack_id)
    if prop_line:
        lines.append(prop_line)
    lines.append(f"Mixes: {mix_count} · Prop PASS: {pass_count}")
    if best and pass_count > 0:
        br = BacktestResult.model_validate(best)
        lines.append(
            f"<b>Best:</b> {escape(best_label)} — PASS {_pnl_trades(br)}"
        )
    elif pass_count == 0 and rows:
        lines.append("<i>No mix passed prop on this period.</i>")
        if best:
            br = BacktestResult.model_validate(best)
            reason = (br.prop_fail_reason or "fail")[:40]
            lines.append(
                f"Top by rank: {escape(best_label)} FAIL {_pnl_trades(br)} ({escape(reason)})"
            )

    lines.append("")
    lines.append(
        "<i>Date range = full history (e.g. 6mo). "
        "Trades = closed SL/TP only. FAIL often = <b>daily loss limit</b> (DLL) on one bad day, "
        "not only max-loss (MLL). Risk/trade = min(template, MLL÷10).</i>"
    )
    lines.append(
        "<i>sig L/S = bars in long/short state (rule hold), not entry count — "
        "mixes can differ a lot but still show 5 closed trades.</i>"
    )
    lines.append("<b>Ranking</b> (PASS first, then PnL):")
    for row in rows[:10]:
        res = row.get("result") or {}
        br = BacktestResult.model_validate(res)
        badge = "PASS" if br.prop_pass else "FAIL"
        lines.append(
            f"{row.get('rank', '?')}. {escape(row.get('mix_label', ''))} — "
            f"{badge} {_pnl_trades(br)}{_signal_hint(row)}"
        )
    return "\n".join(lines)
