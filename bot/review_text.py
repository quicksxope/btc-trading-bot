"""Wizard review summary lines (HTML)."""

from __future__ import annotations

from html import escape

from bot.fsm.validation import BacktestDraft

HOLA_PACK_PREFIX = "holaprime_"
TOPSTEP_PACK_PREFIX = "topstep_"


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
    if draft.wizard_kind == "study":
        from bot.fsm.validation import study_mix_count

        pool = ", ".join(draft.study_pool) if draft.study_pool else "—"
        mixes = study_mix_count(draft.study_pool)
        lines.append(f"Mode: indicator study ({mixes} mixes)")
        lines.append(f"Pool: {escape(pool)}")
        lines.append("Rule: default template AND · primary TF only")
    elif draft.strategy_mode == "preset" and draft.strategy_preset:
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
        from engine.prop_firm import load_prop_pack

        pack = load_prop_pack(draft.prop_pack or "generic")
        pack_title = pack.label or draft.prop_pack or "generic"
        lines.append(f"Prop: {escape(pack_title)}")
        ref = pack.reference_usd or {}
        if ref:
            ref_bits = []
            if ref.get("profit_target") is not None:
                ref_bits.append(f"target ${ref['profit_target']:,.0f}")
            if ref.get("daily_loss") is not None:
                ref_bits.append(f"daily ${ref['daily_loss']:,.0f}")
            if ref.get("max_loss") is not None:
                ref_bits.append(f"max loss ${ref['max_loss']:,.0f}")
            if ref_bits:
                ref_bal = int(pack.initial_balance_usd or draft.initial_balance)
                tag = f"${ref_bal // 1000}k" if ref_bal >= 1000 else f"${ref_bal}"
                lines.append(f"<i>Live ref ({tag}): {escape(', '.join(ref_bits))}</i>")
        if draft.prop_daily_loss_pct is not None and draft.prop_max_dd_pct is not None:
            extra = f"daily {draft.prop_daily_loss_pct:g}% / max DD {draft.prop_max_dd_pct:g}%"
            if draft.prop_profit_target_pct is not None:
                extra += f" / target {draft.prop_profit_target_pct:g}%"
            if draft.prop_min_trading_days is not None:
                extra += f" / min days {draft.prop_min_trading_days}"
            lines.append(f"Engine limits: {extra}")
        exec_defaults = pack.execution_defaults or {}
        if exec_defaults.get("mode") == "sltp_risk":
            from engine.execution_sltp import capped_risk_per_trade_usd
            from engine.models import PropFirmConfig

            rr = draft.execution_risk_reward_ratio
            if rr is None:
                rr = float(exec_defaults.get("risk_reward_ratio", 2.0))
            ref_risk = (pack.reference_usd or {}).get("risk_per_trade")
            tpl_risk = float(
                ref_risk
                or (exec_defaults.get("risk_per_trade_usd") or 0)
            )
            prop_cfg = PropFirmConfig(
                enabled=True,
                pack_id=draft.prop_pack or "generic",
                daily_loss_pct=draft.prop_daily_loss_pct or pack.daily_loss_pct,
                max_drawdown_pct=draft.prop_max_dd_pct or pack.max_drawdown_pct,
            )
            eff_risk = capped_risk_per_trade_usd(
                tpl_risk, prop_cfg, draft.initial_balance
            )
            risk_line = f"risk/trade ≤ ${eff_risk:,.0f}"
            if eff_risk + 1e-6 < tpl_risk:
                risk_line += f" (cap 1/10 max loss; template ${tpl_risk:,.0f})"
            mt = draft.execution_max_trades_per_day
            if mt is None:
                mt = exec_defaults.get("max_trades_per_day")
            mt_s = "∞" if mt is None or mt == 0 else str(int(mt))
            lines.append(
                f"Execution: SL/TP swing · {risk_line} · R:R <b>1:{rr:g}</b> · max trades/day <b>{mt_s}</b>"
            )
        elif pack.engine == "usd":
            lines.append("<i>USD prop engine (no SL/TP template on this pack).</i>")
        rule = draft.prop_consistency_rule
        if rule and rule != "none":
            if rule == "hola_best_day" and draft.prop_consistency_pct:
                lines.append(f"Consistency: Hola best-day ≤ {draft.prop_consistency_pct:g}%")
            elif rule == "topstep_target_ratio":
                lines.append("Consistency: TopStep best-day vs profit target (50%)")
        elif pack.consistency_rule and pack.consistency_rule != "none":
            if pack.consistency_pct:
                lines.append(f"Consistency: template {pack.consistency_pct:g}% rule")

    if draft.session_id:
        lines.append(f"Trading time: {escape(draft.session_id.value)}")

    lines.append(f"Balance: ${draft.initial_balance:,.0f}")
    lines.append(f"Fill: {escape(draft.fill_model)}")
    return "\n".join(lines)


def hola_result_disclaimer(pack_id: str | None) -> str | None:
    if not pack_id:
        return None
    from engine.prop_firm import load_prop_pack

    pack = load_prop_pack(pack_id)
    if pack.engine == "usd" or (pack.execution_defaults or {}).get("mode") == "sltp_risk":
        return "<i>SL/TP + USD risk sizing from prop template when configured.</i>"
    if pack_id.startswith(HOLA_PACK_PREFIX) or pack_id.startswith(TOPSTEP_PACK_PREFIX):
        return "<i>Legacy % prop pack — pick a template with USD engine for Phase B rules.</i>"
    return None
