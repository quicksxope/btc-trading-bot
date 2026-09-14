"""Wizard step copy + navigation targets (user flow: asset → TF → indicator → session → R:R → prop)."""

from __future__ import annotations

from datetime import date, timedelta

from aiogram.types import InlineKeyboardMarkup, Message

from bot.formatting import bold, footer
from bot.fsm.validation import BacktestDraft
from bot.keyboards import (
    date_preset_keyboard,
    primary_tf_keyboard,
    prop_keyboard,
    risk_reward_keyboard,
    session_keyboard,
    strategy_mode_keyboard,
)


def step_asset_title() -> str:
    return bold("1 — Aset") + "\nPilih kelas aset (crypto / CFD)."


def step_instrument_title() -> str:
    return bold("2 — Instrument") + "\nPilih simbol."


def step_timeframe_title() -> str:
    return bold("3 — Timeframe") + "\nPrimary TF untuk sinyal."


def step_indicator_title(draft: BacktestDraft) -> str:
    if draft.wizard_kind == "study":
        return bold("4 — Indikator") + "\nPilih 1–3 indikator (study sweep)."
    return bold("4 — Indikator / strategi") + "\nPreset atau custom rules."


def step_session_title() -> str:
    return (
        bold("5 — Jam trading")
        + "\nSession UTC (entry bar close, fill next open)."
    )


def step_risk_reward_title(draft: BacktestDraft) -> str:
    rr = draft.execution_risk_reward_ratio or 2.0
    return (
        bold("6 — Risk : reward")
        + f"\nTP vs jarak SL (swing). Saat ini <b>1:{rr:g}</b>."
        + "\n<i>Berlaku jika paket prop pakai SL/TP. Max trades/hari diatur setelah pilih prop.</i>"
    )


def step_prop_title() -> str:
    return (
        bold("7 — Prop firm")
        + "\nPaket ter-mapping (Hola, TopStep, …) atau <b>Custom</b> "
        "(max loss, profit, daily, consistency)."
    )


def step_dates_title(extra: str = "") -> str:
    return bold("Periode backtest") + extra


def risk_reward_markup(draft: BacktestDraft) -> InlineKeyboardMarkup:
    return risk_reward_keyboard(draft)


async def show_timeframe(message: Message, draft: BacktestDraft, *, edit: bool = True) -> None:
    text = step_timeframe_title() + footer(draft)
    kb = primary_tf_keyboard()
    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


async def show_indicator_mode(message: Message, draft: BacktestDraft) -> None:
    await message.edit_text(
        step_indicator_title(draft) + footer(draft),
        reply_markup=strategy_mode_keyboard(),
    )


async def show_session(message: Message, draft: BacktestDraft) -> None:
    await message.edit_text(
        step_session_title() + footer(draft),
        reply_markup=session_keyboard(draft),
    )


async def show_risk_reward(message: Message, draft: BacktestDraft) -> None:
    if draft.execution_risk_reward_ratio is None:
        draft.execution_risk_reward_ratio = 2.0
    await message.edit_text(
        step_risk_reward_title(draft) + footer(draft),
        reply_markup=risk_reward_markup(draft),
    )


async def show_prop(message: Message, draft: BacktestDraft, hint: str = "") -> None:
    await message.edit_text(
        step_prop_title() + hint + footer(draft),
        reply_markup=prop_keyboard(),
    )


async def show_dates(message: Message, draft: BacktestDraft, extra: str = "") -> None:
    await message.edit_text(
        step_dates_title(extra) + footer(draft),
        reply_markup=date_preset_keyboard(),
    )


def dates_footer_line(draft: BacktestDraft) -> str:
    if draft.date_from and draft.date_to:
        return f"{draft.date_from} .. {draft.date_to}"
    return "—"
