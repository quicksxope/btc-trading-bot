"""Telegram message templates for jobs and results (HTML)."""

from __future__ import annotations

from html import escape

from engine.models import BacktestResult


def home_status(idle: bool, running: int, queued: int) -> str:
    if running:
        status = f"Running {running} job(s)"
    elif queued:
        status = f"Idle (queue: {queued})"
    else:
        status = "Idle"
    return (
        f"<b>Agnostic Backtest Bot</b>\n"
        f"Status: {escape(status)}\n\n"
        f"<i>Tombol di bawah = menu / (start, new, status, …)</i>"
    )


def job_card(job_id: str, status: str, queue_position: int | None) -> str:
    pos = f" | position {queue_position}" if queue_position is not None else ""
    return f"Job {escape(job_id)} | {escape(status)}{pos}"


def progress_message(job_id: str, stage: str, pct: float) -> str:
    return f"Job <code>{escape(job_id)}</code>\n{escape(stage)}\nProgress: {pct:.0f}%"


def result_summary(
    job_id: str,
    result: BacktestResult,
    semantics: str,
    compare_delta: str | None = None,
    footer_note: str | None = None,
) -> str:
    headline = "PASS prop rules" if result.prop_pass else f"FAIL prop — {result.prop_fail_reason}"
    lines = [
        f"<b>Backtest complete</b> <code>{escape(job_id)}</code>",
        f"<b>{escape(headline)}</b>",
        "",
        f"Net PnL: {result.net_pnl_pct:+.2f}% · {result.trade_count} trades "
        f"({result.wins}W / {result.losses}L)",
        f"Max DD: {result.max_drawdown_pct:.2f}%",
        f"Win rate: {result.win_rate:.1f}%",
        f"Profit factor: {result.profit_factor:.2f}",
        "",
        f"Worst daily: {result.worst_daily_loss_pct:.2f}%",
        f"Trading days: {result.trading_days}",
    ]
    if result.execution_mode and result.execution_mode != "signal_flip":
        lines.append(f"Execution: {escape(result.execution_mode)}")
    if result.prop_engine and result.prop_engine not in ("off", "pct"):
        lines.append(f"Prop engine: {escape(result.prop_engine)}")
    if result.prop_detail:
        lines.append(f"<i>{escape(result.prop_detail)}</i>")
    lines.extend(["", f"<i>{escape(semantics)}</i>"])
    if compare_delta:
        lines.extend(["", compare_delta])
    if footer_note:
        lines.extend(["", footer_note])
    return "\n".join(lines)


def compare_block(
    prev_job: str,
    delta_pnl: float,
    delta_dd: float,
    *,
    prev_prop_pass: bool | None = None,
    cur_prop_pass: bool | None = None,
    prev_fail_reason: str | None = None,
    cur_fail_reason: str | None = None,
) -> str:
    lines = [
        f"<b>Compare vs</b> <code>{escape(prev_job)}</code>",
    ]
    if prev_prop_pass is not None and cur_prop_pass is not None:
        prev_s = "PASS" if prev_prop_pass else f"FAIL ({prev_fail_reason or '—'})"
        cur_s = "PASS" if cur_prop_pass else f"FAIL ({cur_fail_reason or '—'})"
        lines.append(f"Prop: {prev_s} → {cur_s}")
    lines.append(f"Δ PnL: {delta_pnl:+.2f} pp")
    lines.append(f"Δ Max DD: {delta_dd:+.2f} pp")
    return "\n".join(lines)
