"""Telegram text for indicator study results."""

from __future__ import annotations

from html import escape

from engine.models import BacktestResult


def _pnl_trades(br: BacktestResult, *, pnl_decimals: int = 2) -> str:
    base = f"{br.net_pnl_pct:+.{pnl_decimals}f}% · {br.trade_count} trades"
    if br.trade_count and br.trading_days:
        base += f" ({br.trading_days}d w/ exits)"
    return base


def _signal_hint(row: dict) -> str:
    lo = row.get("signal_bars_long")
    sh = row.get("signal_bars_short")
    if lo is None and sh is None:
        return ""
    return f" · sig L{lo}/S{sh} bars"


def study_result_summary(job_id: str, payload: dict, instrument: str, primary_tf: str) -> str:
    rows = payload.get("rows") or []
    pool = payload.get("indicator_pool") or []
    mix_count = payload.get("mix_count") or len(rows)
    pass_count = payload.get("pass_count") or 0
    best_label = payload.get("best_mix_label") or "—"
    best = payload.get("best")

    lines = [
        f"<b>Indicator study</b> <code>{escape(job_id)}</code>",
        f"{escape(instrument)} · {escape(primary_tf)} · pool: {escape('+'.join(pool))}",
        f"Mixes: {mix_count} · Prop PASS: {pass_count}",
    ]
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
        "Trades = closed SL/TP only — Hola ~$1k risk × ~5 SL ≈ max-loss floor, "
        "then no new entries for the rest of the period.</i>"
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
