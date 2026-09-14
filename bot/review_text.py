"""Wizard review summary lines (HTML)."""

from __future__ import annotations

from html import escape

from bot.fsm.validation import BacktestDraft

HOLA_PACK_PREFIX = "holaprime_"


def review_summary_html(draft: BacktestDraft) -> str:
    lines = ["<b>Review</b>"]
    if draft.instrument:
        lines.append(f"Instrument: {escape(draft.instrument.value)}")
    if draft.date_from and draft.date_to:
        lines.append(f"Dates: {draft.date_from} .. {draft.date_to}")
    if draft.primary_tf:
        lines.append(f"Primary TF: {escape(draft.primary_tf)}")
        if draft.context_tfs:
            lines.append(f"Context: {escape(', '.join(draft.context_tfs))}")
    if draft.strategy_mode == "preset" and draft.strategy_preset:
        lines.append(f"Strategy: preset {escape(draft.strategy_preset)}")
        if draft.strategy_preset == "cipher_b" and draft.primary_tf and draft.primary_tf != "30m":
            lines.append(
                "<i>Hint: Cipher B works best on 30m (resampled from 15m in DB).</i>"
            )
    elif draft.strategy_mode == "custom":
        lines.append(f"Strategy: custom ({len(draft.custom_indicators)} indicators)")
        if draft.custom_long_when:
            lines.append(f"Long: {escape(draft.custom_long_when[:80])}")
        if draft.custom_short_when:
            lines.append(f"Short: {escape(draft.custom_short_when[:80])}")

    if draft.prop_pack in (None, "none"):
        lines.append("Prop: off (PnL only)")
    else:
        lines.append(f"Prop pack: {escape(draft.prop_pack or 'generic')}")
        if draft.prop_pack and draft.prop_pack.startswith(HOLA_PACK_PREFIX):
            lines.append(
                "<i>Hola packs: ~% rules only until Phase B "
                "(USD caps, consistency, SL/TP). Use saved preset from examples.</i>"
            )
        elif draft.prop_daily_loss_pct is not None and draft.prop_max_dd_pct is not None:
            extra = f"daily {draft.prop_daily_loss_pct:g}% / max DD {draft.prop_max_dd_pct:g}%"
            if draft.prop_profit_target_pct is not None:
                extra += f" / target {draft.prop_profit_target_pct:g}%"
            if draft.prop_min_trading_days is not None:
                extra += f" / min days {draft.prop_min_trading_days}"
            lines.append(f"Limits: {extra}")

    lines.append(f"Balance: ${draft.initial_balance:,.0f}")
    lines.append(f"Fill: {escape(draft.fill_model)}")
    return "\n".join(lines)


def hola_result_disclaimer(pack_id: str | None) -> str | None:
    if not pack_id or not pack_id.startswith(HOLA_PACK_PREFIX):
        return None
    return (
        "<i>Hola pack: approximate % rules only — not full USD/consistency/SL·TP (Phase B).</i>"
    )
