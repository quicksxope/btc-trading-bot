"""Format trade logs for Telegram (HTML)."""

from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd


def _px(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    x = float(v)
    if abs(x) >= 1000:
        return f"{x:,.2f}"
    if abs(x) >= 1:
        return f"{x:.2f}"
    return f"{x:.5f}"


def _usd(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"${float(v):,.2f}"


def _ts_short(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    s = str(v).replace("T", " ")
    return s[:16] if len(s) > 16 else s


def format_trades_html(
    trades: pd.DataFrame | list[dict[str, Any]],
    *,
    limit: int = 12,
    title: str = "Trade log",
) -> str:
    if isinstance(trades, list):
        df = pd.DataFrame(trades) if trades else pd.DataFrame()
    else:
        df = trades
    if df.empty:
        return f"<b>{escape(title)}</b>\n<i>No closed trades.</i>"

    has_levels = "entry_price" in df.columns and "stop_loss" in df.columns
    lines = [f"<b>{escape(title)}</b>"]
    if len(df) > limit:
        lines.append(f"<i>Last {limit} of {len(df)} (full list in trades.csv)</i>")
    else:
        lines.append(f"<i>{len(df)} trade(s)</i>")

    tail = df.tail(limit)
    start_n = len(df) - len(tail) + 1
    for j, (_, r) in enumerate(tail.iterrows()):
        i = start_n + j
        side = str(r.get("side", "")).upper()[:1] or "?"
        pnl = float(r.get("pnl") or 0)
        reason = str(r.get("exit_reason") or "—")
        rm = r.get("r_multiple")
        rm_s = f" · {float(rm):+.2f}R" if rm is not None and not pd.isna(rm) else ""

        if has_levels and r.get("entry_price") is not None and not pd.isna(r.get("entry_price")):
            lines.append(
                f"{i}. {side} {_ts_short(r.get('entry_time'))}→{_ts_short(r.get('exit_time'))} "
                f"in {_px(r.get('entry_price'))} "
                f"SL {_px(r.get('stop_loss'))} TP {_px(r.get('take_profit'))} "
                f"· risk {_usd(r.get('risk_usd'))} "
                f"→ {escape(reason.upper())} {_usd(pnl)}{rm_s}"
            )
        else:
            lines.append(
                f"{i}. {side} {_ts_short(r.get('exit_time'))} "
                f"→ {_usd(pnl)} ({escape(reason)})"
            )
    return "\n".join(lines)
