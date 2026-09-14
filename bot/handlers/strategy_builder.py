"""Guided custom strategy builder (indicators + DSL rules)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.formatting import bold, footer
from bot.fsm.validation import BacktestDraft, ValidationError
from bot.handlers.wizard import _load_draft, _save_draft
from bot.keyboards import nav_row, prop_keyboard
from bot.states import WizardStates
from bot.wizard_nav import push_step
from engine.catalog import indicator_ids, load_rule_templates

router = Router()


def _indicator_pick_keyboard() -> InlineKeyboardMarkup:
    rows = []
    row: list[InlineKeyboardButton] = []
    for ind in indicator_ids():
        row.append(InlineKeyboardButton(text=ind, callback_data=f"wiz:sb:pick:{ind}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(nav_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _builder_keyboard(draft: BacktestDraft) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="+ Add indicator", callback_data="wiz:sb:add")],
        [InlineKeyboardButton(text="Rule templates", callback_data="wiz:sb:templates")],
        [
            InlineKeyboardButton(text="Set long rule (text)", callback_data="wiz:sb:long"),
            InlineKeyboardButton(text="Set short rule", callback_data="wiz:sb:short"),
        ],
        [InlineKeyboardButton(text="Continue »", callback_data="wiz:sb:done")],
        nav_row(),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _builder_text(draft: BacktestDraft) -> str:
    lines = [bold("Custom strategy (guided)"), f"Indicators: {len(draft.custom_indicators)}"]
    for i, spec in enumerate(draft.custom_indicators, 1):
        lines.append(
            f"  {i}. {spec.get('name')} @ {spec.get('timeframe', 'primary')} {spec.get('params', {})}"
        )
    if draft.custom_long_when:
        lines.append(f"Long: {draft.custom_long_when[:120]}")
    if draft.custom_short_when:
        lines.append(f"Short: {draft.custom_short_when[:120]}")
    if draft.custom_rule and not draft.custom_long_when:
        lines.append(f"Legacy rule: {draft.custom_rule}")
    return "\n".join(lines)


async def show_strategy_builder(message, draft: BacktestDraft, *, edit: bool = True) -> None:
    text = _builder_text(draft) + footer(draft)
    if edit:
        await message.edit_text(text, reply_markup=_builder_keyboard(draft))
    else:
        await message.answer(text, reply_markup=_builder_keyboard(draft))


@router.callback_query(F.data == "wiz:sb:add")
async def sb_add(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "Pick indicator" + footer(_load_draft(await state.get_data())),
        reply_markup=_indicator_pick_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:sb:pick:"))
async def sb_pick_indicator(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    ind = callback.data.split(":")[-1]
    tf = draft.primary_tf or "primary"
    tfs = ["primary", *draft.context_tfs]
    rows = [[InlineKeyboardButton(text=t, callback_data=f"wiz:sb:tf:{ind}:{t}") for t in tfs]]
    rows.append(nav_row())
    await callback.message.edit_text(
        f"TF for {ind}?" + footer(draft),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:sb:tf:"))
async def sb_pick_tf(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    parts = callback.data.split(":")
    ind, tf = parts[3], parts[4]
    from engine.catalog import indicator_meta

    meta = indicator_meta(ind)
    params = {}
    for pname, pdef in (meta.get("params") or {}).items():
        params[pname] = pdef.get("default", 14)
    draft.custom_indicators.append({"name": ind, "timeframe": tf, "params": params})
    await state.update_data(**_save_draft(data, draft))
    await show_strategy_builder(callback.message, draft)
    await callback.answer()


@router.callback_query(F.data == "wiz:sb:templates")
async def sb_templates(callback: CallbackQuery, state: FSMContext) -> None:
    templates = load_rule_templates().get("templates", {})
    rows = []
    for tid, t in templates.items():
        rows.append([InlineKeyboardButton(text=t.get("label", tid), callback_data=f"wiz:sb:tmpl:{tid}")])
    rows.append(nav_row())
    await callback.message.edit_text(
        "Rule template" + footer(_load_draft(await state.get_data())),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:sb:tmpl:"))
async def sb_apply_template(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    tid = callback.data.split(":")[-1]
    templates = load_rule_templates().get("templates", {})
    t = templates.get(tid)
    if not t:
        await callback.answer("Unknown template", show_alert=True)
        return
    draft.custom_long_when = t.get("long_when", "")
    draft.custom_short_when = t.get("short_when", "")
    for spec in t.get("requires_indicators", []):
        if spec not in draft.custom_indicators:
            draft.custom_indicators.append(spec)
    await state.update_data(**_save_draft(data, draft))
    await show_strategy_builder(callback.message, draft)
    await callback.answer("Template applied")


@router.callback_query(F.data == "wiz:sb:long")
async def sb_long_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WizardStates.custom_rule_long)
    await callback.message.edit_text(
        "Kirim DSL long_when, contoh:\n<code>primary_RSI_value &lt; 30</code>"
    )
    await callback.answer()


@router.callback_query(F.data == "wiz:sb:short")
async def sb_short_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WizardStates.custom_rule_short)
    await callback.message.edit_text(
        "Kirim DSL short_when, contoh:\n<code>primary_RSI_value &gt; 70</code>"
    )
    await callback.answer()


@router.message(WizardStates.custom_rule_long)
async def sb_long_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    draft.custom_long_when = message.text.strip()
    try:
        from engine.rules import validate_expression

        validate_expression(draft.custom_long_when)
    except ValueError as e:
        await message.answer(f"Invalid: {e}")
        return
    await state.set_state(WizardStates.active)
    await state.update_data(**_save_draft(data, draft))
    await show_strategy_builder(message, draft, edit=False)


@router.message(WizardStates.custom_rule_short)
async def sb_short_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    draft.custom_short_when = message.text.strip()
    try:
        from engine.rules import validate_expression

        validate_expression(draft.custom_short_when)
    except ValueError as e:
        await message.answer(f"Invalid: {e}")
        return
    await state.set_state(WizardStates.active)
    await state.update_data(**_save_draft(data, draft))
    await show_strategy_builder(message, draft, edit=False)


@router.callback_query(F.data == "wiz:sb:done")
async def sb_done(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    try:
        from bot.fsm.validation import validate_strategy

        validate_strategy(draft)
    except ValidationError as e:
        await callback.answer(str(e), show_alert=True)
        return
    from bot import wizard_steps
    from bot.keyboards import session_keyboard

    await push_step(state, "session")
    await callback.message.edit_text(
        wizard_steps.step_session_title() + footer(draft),
        reply_markup=session_keyboard(draft),
    )
    await callback.answer()
