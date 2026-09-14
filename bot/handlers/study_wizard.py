"""Indicator study wizard (1–3 indicators, subset sweep)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.formatting import bold, footer
from bot.fsm.validation import BacktestDraft, study_mix_count
from bot.handlers.wizard import _load_draft, _save_draft
from bot.keyboards import nav_row, session_keyboard, study_pool_keyboard
from bot.wizard_nav import push_step
from storage.db import Database

router = Router()


def _pool_text(draft: BacktestDraft) -> str:
    n = len(draft.study_pool)
    mixes = study_mix_count(draft.study_pool) if n else 0
    sel = ", ".join(draft.study_pool) if draft.study_pool else "—"
    return (
        bold("Indicator study — pick 1–3")
        + f"\nSelected ({n}/3): {sel}"
        + f"\nWill run <b>{mixes}</b> mix(es) · rule: default AND · primary TF only"
        + footer(draft)
    )


@router.callback_query(F.data.startswith("wiz:study:toggle:"))
async def study_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    ind = callback.data.split(":")[-1].upper()
    if ind in draft.study_pool:
        draft.study_pool.remove(ind)
    elif len(draft.study_pool) >= 3:
        await callback.answer("Max 3 indicators", show_alert=True)
        return
    else:
        draft.study_pool.append(ind)
    await state.update_data(**_save_draft(data, draft))
    await callback.message.edit_text(
        _pool_text(draft),
        reply_markup=study_pool_keyboard(draft.study_pool),
    )
    await callback.answer()


@router.callback_query(F.data == "wiz:study:load_last")
async def study_load_last(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    last = await db.get_last_indicator_favorite(callback.from_user.id)
    if not last:
        await callback.answer("No saved pool yet", show_alert=True)
        return
    draft.study_pool = last[:3]
    await state.update_data(**_save_draft(data, draft))
    await callback.message.edit_text(
        _pool_text(draft),
        reply_markup=study_pool_keyboard(draft.study_pool),
    )
    await callback.answer("Loaded last pool")


@router.callback_query(F.data == "wiz:study:done")
async def study_pool_done(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.fsm.validation import validate_study_pool, ValidationError

    data = await state.get_data()
    draft = _load_draft(data)
    try:
        validate_study_pool(draft)
    except ValidationError as e:
        await callback.answer(str(e), show_alert=True)
        return
    draft.context_tfs = []
    await state.update_data(**_save_draft(data, draft))
    from bot import wizard_steps

    await push_step(state, "session")
    await callback.message.edit_text(
        wizard_steps.step_session_title()
        + "\nStudy: session sama untuk semua mix."
        + footer(draft),
        reply_markup=session_keyboard(draft),
    )
    await callback.answer()


async def show_study_pool(message, draft: BacktestDraft, *, edit: bool = True) -> None:
    text = _pool_text(draft)
    kb = study_pool_keyboard(draft.study_pool)
    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)
