"""Wizard FSM handlers."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, timedelta
from html import escape as html_escape

import yaml
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.fsm.validation import (
    BacktestDraft,
    ValidationError,
    apply_date_preset,
    draft_to_config,
    ensure_default_dates,
)
from bot import wizard_steps
from bot.keyboards import (
    asset_class_keyboard,
    balance_keyboard,
    context_tf_keyboard,
    date_preset_keyboard,
    instrument_keyboard,
    primary_tf_keyboard,
    prop_custom_keyboard,
    prop_keyboard,
    prop_params_keyboard,
    prop_template_keyboard,
    review_keyboard,
    session_keyboard,
    session_toggles_keyboard,
    strategy_mode_keyboard,
    strategy_preset_keyboard,
)
from engine.prop_firm import load_prop_pack
from bot.handlers.home import show_home
from bot.states import WizardStates
from engine.instruments import catalog_entry, load_instrument_profile
from engine.models import InstrumentId, SessionId
from engine.prop_firm import instrument_allowed
from storage.db import Database
from bot.formatting import bold, code, footer, pre
from bot.review_text import review_summary_html
from storage.templates import job_card

router = Router()


@router.callback_query(F.data == "home:new")
async def start_wizard(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.wizard_nav import clear_stack, push_step

    await state.clear()
    draft = BacktestDraft()
    await state.update_data(draft=draft.__dict__)
    await state.set_state(WizardStates.active)
    await clear_stack(state)
    await push_step(state, "asset")
    try:
        await callback.message.edit_text(
            wizard_steps.step_asset_title() + footer(draft),
            reply_markup=asset_class_keyboard(),
        )
    finally:
        await callback.answer()


def _load_draft(data: dict) -> BacktestDraft:
    d = BacktestDraft()
    for k, v in data.get("draft", {}).items():
        if k == "instrument" and v:
            setattr(d, k, InstrumentId(v))
        elif k == "session_id" and v:
            setattr(d, k, SessionId(v))
        elif hasattr(d, k):
            setattr(d, k, v)
    return d


def _save_draft(data: dict, draft: BacktestDraft) -> dict:
    raw = draft.__dict__.copy()
    if raw.get("instrument"):
        raw["instrument"] = raw["instrument"].value
    if raw.get("session_id"):
        raw["session_id"] = raw["session_id"].value
    data["draft"] = raw
    return data


@router.callback_query(F.data.startswith("wiz:ac:"))
async def pick_asset(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.wizard_nav import push_step

    try:
        data = await state.get_data()
        draft = _load_draft(data)
        draft.asset_class = callback.data.split(":")[-1]  # type: ignore[assignment]
        await state.update_data(**_save_draft(data, draft))
        await push_step(state, "instrument")
        await callback.message.edit_text(
            wizard_steps.step_instrument_title() + footer(draft),
            reply_markup=instrument_keyboard(draft),
        )
    except Exception:
        logging.exception("pick_asset failed")
        await callback.answer("Gagal memuat instrument. Coba lagi atau /new.", show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:inst:"))
async def pick_instrument(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.wizard_nav import push_step

    data = await state.get_data()
    draft = _load_draft(data)
    inst = InstrumentId(callback.data.split(":")[-1])
    draft.instrument = inst
    cat = catalog_entry(inst)
    extra = ""
    if cat:
        src = cat.get("source", "local")
        extra = (
            f"\nData ({src}): {cat.get('available_from')} .. {cat.get('available_to')}"
            f" — {cat.get('data_symbol')}"
        )
    prof = load_instrument_profile(inst)
    from engine.warehouse import coverage_summary_lines

    cov_lines = await asyncio.to_thread(coverage_summary_lines, prof.data_symbol)
    if cov_lines:
        extra += "\n" + "\n".join(html_escape(line) for line in cov_lines)
    ensure_default_dates(draft, "6mo")
    await state.update_data(**_save_draft(data, draft))
    await push_step(state, "timeframe_primary")
    extra += f"\nPeriode default: {wizard_steps.dates_footer_line(draft)} (ubah di Review)."
    await callback.message.edit_text(
        wizard_steps.step_timeframe_title() + extra + footer(draft),
        reply_markup=primary_tf_keyboard(),
    )
    await callback.answer()


def _apply_date_preset(preset: str, draft: BacktestDraft) -> tuple[date, date]:
    return apply_date_preset(preset, draft)


@router.callback_query(F.data.startswith("wiz:date:"))
async def pick_date(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.wizard_nav import push_step

    data = await state.get_data()
    draft = _load_draft(data)
    kind = callback.data.split(":")[-1]
    if kind == "custom":
        await state.set_state(WizardStates.custom_date)
        await callback.message.edit_text(
            "Kirim tanggal: " + code("YYYY-MM-DD to YYYY-MM-DD") + footer(draft)
        )
        await callback.answer()
        return
    draft.date_from, draft.date_to = _apply_date_preset(kind, draft)
    await state.update_data(**_save_draft(data, draft))
    if data.get("dates_return") == "review":
        await state.update_data(dates_return=None)
        await push_step(state, "review")
        await _show_review(callback.message, state, draft)
        await callback.answer()
        return
    await push_step(state, "session")
    await wizard_steps.show_session(callback.message, draft)
    await callback.answer()


@router.message(WizardStates.custom_date)
async def custom_date_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    try:
        a, b = message.text.replace(" ", "").split("to")
        draft.date_from = date.fromisoformat(a)
        draft.date_to = date.fromisoformat(b)
        from bot.fsm.validation import validate_date_range

        validate_date_range(draft)
    except Exception:
        await message.answer("Format invalid. Contoh: 2024-01-01 to 2024-06-30")
        return
    from bot.wizard_nav import push_step

    await state.set_state(WizardStates.active)
    await state.update_data(**_save_draft(data, draft))
    await push_step(state, "session")
    await message.answer(
        wizard_steps.step_session_title() + footer(draft),
        reply_markup=session_keyboard(draft),
    )


@router.callback_query(F.data.startswith("wiz:sess:"))
async def pick_session(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.wizard_nav import push_step

    data = await state.get_data()
    draft = _load_draft(data)
    sid = callback.data.split(":")[-1]
    if sid == "advanced":
        await push_step(state, "session_toggles")
        await callback.message.edit_text(
            bold("Session — advanced") + footer(draft),
            reply_markup=session_toggles_keyboard(draft),
        )
        await callback.answer()
        return
    draft.session_id = SessionId(sid)
    if draft.asset_class == "cfd":
        draft.session_trading = True
        draft.session_accounting = True
    await state.update_data(**_save_draft(data, draft))
    await push_step(state, "risk_reward")
    await wizard_steps.show_risk_reward(callback.message, draft)
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:stoggle:"))
async def session_toggles(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.wizard_nav import push_step

    data = await state.get_data()
    draft = _load_draft(data)
    action = callback.data.split(":")[-1]
    if action == "trade":
        draft.session_trading = not draft.session_trading
    elif action == "acct":
        draft.session_accounting = not draft.session_accounting
    elif action == "utc":
        draft.prop_daily_reset_utc = not draft.prop_daily_reset_utc
    elif action == "done":
        await push_step(state, "risk_reward")
        await wizard_steps.show_risk_reward(callback.message, draft)
        await callback.answer()
        return
    await state.update_data(**_save_draft(data, draft))
    await callback.message.edit_text(
        bold("Session toggles") + footer(draft),
        reply_markup=session_toggles_keyboard(draft),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:ptf:"))
async def pick_primary_tf(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.wizard_nav import push_step

    data = await state.get_data()
    draft = _load_draft(data)
    draft.primary_tf = callback.data.split(":")[-1]
    await state.update_data(**_save_draft(data, draft))
    if draft.wizard_kind == "study":
        from bot.handlers.study_wizard import show_study_pool

        await push_step(state, "study_pool")
        await show_study_pool(callback.message, draft)
        await callback.answer()
        return
    await push_step(state, "strategy_mode")
    await wizard_steps.show_indicator_mode(callback.message, draft)
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:ctf:"))
async def pick_context_tf(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.wizard_nav import push_step

    data = await state.get_data()
    draft = _load_draft(data)
    tf = callback.data.split(":")[-1]
    if tf == "done":
        try:
            from bot.fsm.validation import validate_timeframes

            validate_timeframes(draft)
        except ValidationError as e:
            await callback.answer(str(e), show_alert=True)
            return
        await push_step(state, "strategy_mode")
        await callback.message.edit_text(
            bold("Step 6 — Strategy") + footer(draft),
            reply_markup=strategy_mode_keyboard(),
        )
        await callback.answer()
        return
    if tf in draft.context_tfs:
        draft.context_tfs.remove(tf)
    else:
        draft.context_tfs.append(tf)
    await state.update_data(**_save_draft(data, draft))
    await callback.message.edit_text(
        bold("Context timeframes") + footer(draft),
        reply_markup=context_tf_keyboard(draft.context_tfs),
    )
    await callback.answer()


@router.callback_query(F.data == "wiz:str:context")
async def strategy_context_optional(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.wizard_nav import push_step

    data = await state.get_data()
    draft = _load_draft(data)
    await push_step(state, "timeframe_context")
    await callback.message.edit_text(
        bold("Context TF (optional)") + footer(draft),
        reply_markup=context_tf_keyboard(draft.context_tfs),
    )
    await callback.answer()


@router.callback_query(F.data == "wiz:str:preset")
async def strategy_preset_mode(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.wizard_nav import push_step

    data = await state.get_data()
    draft = _load_draft(data)
    draft.strategy_mode = "preset"
    await state.update_data(**_save_draft(data, draft))
    await push_step(state, "strategy_detail")
    await callback.message.edit_text(
        "Pilih preset" + footer(draft),
        reply_markup=strategy_preset_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "wiz:str:custom")
async def strategy_custom_mode(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.handlers.strategy_builder import show_strategy_builder
    from bot.wizard_nav import push_step

    data = await state.get_data()
    draft = _load_draft(data)
    draft.strategy_mode = "custom"
    await state.update_data(**_save_draft(data, draft))
    await push_step(state, "strategy_detail")
    await show_strategy_builder(callback.message, draft)
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:sp:"))
async def pick_strategy_preset(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.wizard_nav import push_step

    data = await state.get_data()
    draft = _load_draft(data)
    draft.strategy_preset = callback.data.split(":")[-1]
    await state.update_data(**_save_draft(data, draft))
    await push_step(state, "session")
    hint = ""
    if draft.strategy_preset == "cipher_b":
        hint = "\n<i>Disarankan primary 30m (Coinbase: resample dari 15m).</i>"
    await callback.message.edit_text(
        wizard_steps.step_session_title() + hint + footer(draft),
        reply_markup=session_keyboard(draft),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:prop:"))
async def pick_prop(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.wizard_nav import push_step

    data = await state.get_data()
    draft = _load_draft(data)
    pack = callback.data.split(":")[-1]
    draft.prop_pack = pack
    if pack == "none":
        draft.execution_risk_reward_ratio = None
        await state.update_data(**_save_draft(data, draft))
        await push_step(state, "balance")
        await callback.message.edit_text(
            bold("Step 8 — Balance") + "\nFill: next bar open (locked v0)" + footer(draft),
            reply_markup=balance_keyboard(),
        )
        await callback.answer()
        return
    if draft.instrument:
        ok, msg = instrument_allowed(pack, draft.instrument)
        if not ok:
            await callback.answer(msg, show_alert=True)
            return
    await state.update_data(**_save_draft(data, draft))
    if pack == "templates":
        await push_step(state, "prop_params")
        await callback.message.edit_text(
            "Prop template" + footer(draft),
            reply_markup=prop_template_keyboard(),
        )
        await callback.answer()
        return
    if pack == "custom":
        draft.prop_pack = "generic"
        draft.prop_consistency_rule = None
        draft.prop_consistency_pct = None
        await state.update_data(**_save_draft(data, draft))
        await push_step(state, "prop_params")
        await callback.message.edit_text(
            bold("Custom prop")
            + "\nMax loss = max DD % · daily loss % · profit target · min days · consistency."
            + footer(draft),
            reply_markup=prop_custom_keyboard(draft),
        )
        await callback.answer()
        return
    if pack == "generic":
        await state.update_data(**_save_draft(data, draft))
        await push_step(state, "prop_params")
        await callback.message.edit_text(
            "Generic params" + footer(draft),
            reply_markup=prop_params_keyboard(draft),
        )
    else:
        _apply_prop_template(draft, pack)
        await state.update_data(**_save_draft(data, draft))
        await push_step(state, "prop_params")
        await callback.message.edit_text(
            f"Pack {code(pack)} — adjust or Continue" + footer(draft),
            reply_markup=prop_custom_keyboard(draft),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:prop:load:"))
async def load_prop_template_cb(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.wizard_nav import push_step

    data = await state.get_data()
    draft = _load_draft(data)
    pack_id = callback.data.split(":")[-1]
    if draft.instrument:
        ok, msg = instrument_allowed(pack_id, draft.instrument)
        if not ok:
            await callback.answer(msg, show_alert=True)
            return
    draft.prop_pack = pack_id
    _apply_prop_template(draft, pack_id)
    await state.update_data(**_save_draft(data, draft))
    pack = load_prop_pack(pack_id)
    title = pack.label or pack_id
    await push_step(state, "prop_params")
    await callback.message.edit_text(
        bold(title)
        + "\nSesuaikan limit % / consistency atau Continue."
        + footer(draft),
        reply_markup=prop_custom_keyboard(draft),
    )
    await callback.answer()


def _apply_prop_template(draft: BacktestDraft, pack_id: str) -> None:
    pack = load_prop_pack(pack_id)
    draft.prop_daily_loss_pct = pack.daily_loss_pct
    draft.prop_max_dd_pct = pack.max_drawdown_pct
    draft.prop_profit_target_pct = pack.profit_target_pct
    draft.prop_min_trading_days = pack.min_trading_days
    if pack.initial_balance_usd is not None:
        draft.initial_balance = float(pack.initial_balance_usd)
    defaults = pack.execution_defaults or {}
    if defaults.get("mode") == "sltp_risk":
        if draft.execution_risk_reward_ratio is None:
            draft.execution_risk_reward_ratio = float(defaults.get("risk_reward_ratio", 2.0))
        mt = defaults.get("max_trades_per_day")
        draft.execution_max_trades_per_day = int(mt) if mt is not None else 0
    rule = pack.consistency_rule or "none"
    if rule != "none":
        draft.prop_consistency_rule = rule
        draft.prop_consistency_pct = pack.consistency_pct
    else:
        draft.prop_consistency_rule = None
        draft.prop_consistency_pct = None


async def _finish_prop_params(message: Message, state: FSMContext, draft: BacktestDraft) -> None:
    from bot.wizard_nav import push_step

    data = await state.get_data()
    await state.update_data(**_save_draft(data, draft))
    if draft.prop_pack in (None, "none"):
        await push_step(state, "balance")
        await message.edit_text(
            bold("Balance") + footer(draft),
            reply_markup=balance_keyboard(),
        )
        return
    pack = load_prop_pack(draft.prop_pack or "generic")
    if pack.initial_balance_usd is not None or draft.initial_balance:
        await push_step(state, "review")
        await _show_review(message, state, draft)
        return
    await push_step(state, "balance")
    await message.edit_text(
        bold("Balance") + footer(draft),
        reply_markup=balance_keyboard(),
    )


def _prop_params_title(draft: BacktestDraft) -> str:
    if draft.prop_pack and draft.prop_pack not in ("none", "generic", "templates"):
        return f"Template {code(draft.prop_pack)}"
    if draft.prop_pack == "generic":
        return bold("Custom prop")
    return "Generic params"


def _prop_params_markup(draft: BacktestDraft) -> InlineKeyboardMarkup:
    if draft.prop_pack == "generic":
        return prop_params_keyboard(draft)
    return prop_custom_keyboard(draft)


def _prop_params_body(draft: BacktestDraft, title: str) -> str:
    from bot.fsm.validation import pack_uses_sltp_risk

    extra = ""
    if pack_uses_sltp_risk(draft.prop_pack):
        rr = draft.execution_risk_reward_ratio or 2.0
        extra = f"\nRisk:reward: <b>1:{rr:g}</b>"
        mt = draft.execution_max_trades_per_day
        if mt is None:
            mt = 0
        mt_label = "∞ (no cap)" if mt == 0 else str(mt)
        extra += f"\nMax trades/day: <b>{mt_label}</b>"
    return title + extra + footer(draft)


@router.callback_query(F.data.startswith("wiz:rr:"))
async def pick_risk_reward(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.wizard_nav import push_step

    data = await state.get_data()
    draft = _load_draft(data)
    token = callback.data.split(":")[-1]
    if token == "done":
        await state.update_data(**_save_draft(data, draft))
        await push_step(state, "prop")
        await wizard_steps.show_prop(callback.message, draft)
        await callback.answer()
        return
    draft.execution_risk_reward_ratio = float(token)
    await state.update_data(**_save_draft(data, draft))
    await wizard_steps.show_risk_reward(callback.message, draft)
    await callback.answer("R:R updated")


@router.callback_query(F.data.startswith("wiz:propp:"))
async def prop_params(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    parts = callback.data.split(":")
    if len(parts) >= 4 and parts[2] == "mt":
        draft.execution_max_trades_per_day = int(parts[3])
        await state.update_data(**_save_draft(data, draft))
        title = _prop_params_title(draft)
        await callback.message.edit_text(
            _prop_params_body(draft, title),
            reply_markup=_prop_params_markup(draft),
        )
        await callback.answer("Max trades/day updated")
        return
    if len(parts) >= 4 and parts[2] == "cons":
        tag = parts[3]
        if tag == "none":
            draft.prop_consistency_rule = "none"
            draft.prop_consistency_pct = None
        elif tag == "hola20":
            draft.prop_consistency_rule = "hola_best_day"
            draft.prop_consistency_pct = 20.0
        elif tag == "top50":
            draft.prop_consistency_rule = "topstep_target_ratio"
            draft.prop_consistency_pct = None
        await state.update_data(**_save_draft(data, draft))
        title = _prop_params_title(draft)
        await callback.message.edit_text(
            _prop_params_body(draft, title),
            reply_markup=_prop_params_markup(draft),
        )
        await callback.answer("Consistency updated")
        return
    p = parts[-1]
    if p == "d5":
        draft.prop_daily_loss_pct = 5.0
    elif p == "d4":
        draft.prop_daily_loss_pct = 4.0
    elif p == "d3":
        draft.prop_daily_loss_pct = 3.0
    elif p == "dd10":
        draft.prop_max_dd_pct = 10.0
    elif p == "dd8":
        draft.prop_max_dd_pct = 8.0
    elif p == "dd6":
        draft.prop_max_dd_pct = 6.0
    elif p == "pt10":
        draft.prop_profit_target_pct = 10.0
    elif p == "pt0":
        draft.prop_profit_target_pct = None
    elif p == "min2":
        draft.prop_min_trading_days = 2
    elif p == "min4":
        draft.prop_min_trading_days = 4
    elif p == "done":
        await _finish_prop_params(callback.message, state, draft)
        await callback.answer()
        return
    await state.update_data(**_save_draft(data, draft))
    title = _prop_params_title(draft)
    await callback.message.edit_text(
        _prop_params_body(draft, title),
        reply_markup=_prop_params_markup(draft),
    )
    await callback.answer("Updated")


@router.callback_query(F.data.startswith("wiz:bal:"))
async def pick_balance(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.wizard_nav import push_step

    data = await state.get_data()
    draft = _load_draft(data)
    bal = callback.data.split(":")[-1]
    if bal == "custom":
        await state.set_state(WizardStates.custom_balance)
        await callback.message.edit_text("Kirim balance angka, mis. 75000")
        await callback.answer()
        return
    draft.initial_balance = float(bal)
    await state.update_data(**_save_draft(data, draft))
    await push_step(state, "review")
    await _show_review(callback.message, state, draft)
    await callback.answer()


@router.message(WizardStates.custom_balance)
async def custom_balance(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    try:
        draft.initial_balance = float(message.text.strip())
    except ValueError:
        await message.answer("Angka tidak valid")
        return
    await state.set_state(WizardStates.active)
    await state.update_data(**_save_draft(data, draft))
    text = _review_message(draft)
    await message.answer(text + footer(draft), reply_markup=review_keyboard())


def _review_message(draft: BacktestDraft) -> str:
    cfg = draft_to_config(draft)
    yaml_body = yaml.safe_dump(cfg.to_yaml_dict(), sort_keys=False)[:2000]
    return review_summary_html(draft) + "\n\n" + pre(yaml_body)


async def _show_review(message: Message, state: FSMContext, draft: BacktestDraft) -> None:
    text = _review_message(draft)
    await message.edit_text(text + footer(draft), reply_markup=review_keyboard())


@router.callback_query(F.data == "wiz:run")
async def run_backtest(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    try:
        cfg = draft_to_config(draft)
    except ValidationError as e:
        await callback.answer(str(e), show_alert=True)
        return
    running, queued = await db.count_active(callback.from_user.id)
    if running + queued >= 3:
        await callback.answer("Queue limit (3). Tunggu job selesai.", show_alert=True)
        return
    job_id = uuid.uuid4().hex[:8]
    yaml_text = yaml.safe_dump(cfg.to_yaml_dict(), sort_keys=False)
    await db.create_job(
        job_id,
        callback.from_user.id,
        yaml_text,
        chat_id=callback.message.chat.id,
    )
    if draft.wizard_kind == "study" and draft.study_pool:
        await db.save_indicator_favorite(callback.from_user.id, draft.study_pool)
    pos = await db.queue_position(job_id)
    label = "Study queued" if draft.wizard_kind == "study" else "Queued"
    await callback.message.edit_text(job_card(job_id, "queued", pos))
    await state.clear()
    await callback.answer(label)


@router.callback_query(F.data == "wiz:save_preset")
async def save_preset_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WizardStates.preset_name)
    await callback.message.edit_text("Nama preset?")
    await callback.answer()


@router.message(WizardStates.preset_name)
async def save_preset_name(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    try:
        cfg = draft_to_config(draft)
    except ValidationError as e:
        await message.answer(str(e))
        return
    name = message.text.strip()[:64]
    await db.save_preset(message.from_user.id, name, yaml.safe_dump(cfg.to_yaml_dict()))
    await state.clear()
    await message.answer(f"Preset {code(name)} saved.")


@router.callback_query(F.data == "wiz:review:dates")
async def review_change_dates(callback: CallbackQuery, state: FSMContext) -> None:
    from bot.wizard_nav import push_step

    data = await state.get_data()
    draft = _load_draft(data)
    await state.update_data(dates_return="review")
    await push_step(state, "dates")
    await callback.message.edit_text(
        wizard_steps.step_dates_title() + footer(draft),
        reply_markup=date_preset_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "wiz:cancel")
async def cancel_wizard(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.clear()
    await show_home(callback.message, callback.from_user.id, db, edit=True)
    await callback.answer()


@router.callback_query(F.data == "wiz:back")
async def wizard_back(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    from bot.handlers.strategy_builder import show_strategy_builder
    from bot.wizard_nav import pop_step

    prev = await pop_step(state)
    if not prev:
        await show_home(callback.message, callback.from_user.id, db, edit=True)
        await callback.answer()
        return
    data = await state.get_data()
    draft = _load_draft(data)
    if prev == "asset":
        await callback.message.edit_text(
            wizard_steps.step_asset_title() + footer(draft),
            reply_markup=asset_class_keyboard(),
        )
    elif prev == "instrument":
        await callback.message.edit_text(
            wizard_steps.step_instrument_title() + footer(draft),
            reply_markup=instrument_keyboard(draft),
        )
    elif prev == "dates":
        await callback.message.edit_text(
            wizard_steps.step_dates_title() + footer(draft),
            reply_markup=date_preset_keyboard(),
        )
    elif prev == "timeframe_primary":
        await callback.message.edit_text(
            wizard_steps.step_timeframe_title() + footer(draft),
            reply_markup=primary_tf_keyboard(),
        )
    elif prev == "timeframe_context":
        await callback.message.edit_text(
            bold("Context timeframes") + footer(draft),
            reply_markup=context_tf_keyboard(draft.context_tfs),
        )
    elif prev == "study_pool":
        from bot.handlers.study_wizard import show_study_pool

        await show_study_pool(callback.message, draft)
    elif prev == "strategy_mode":
        await callback.message.edit_text(
            wizard_steps.step_indicator_title(draft) + footer(draft),
            reply_markup=strategy_mode_keyboard(),
        )
    elif prev == "session":
        await wizard_steps.show_session(callback.message, draft)
    elif prev == "session_toggles":
        await callback.message.edit_text(
            bold("Session — advanced") + footer(draft),
            reply_markup=session_toggles_keyboard(draft),
        )
    elif prev == "risk_reward":
        await wizard_steps.show_risk_reward(callback.message, draft)
    elif prev == "strategy_detail":
        if draft.strategy_mode == "custom":
            await show_strategy_builder(callback.message, draft)
        else:
            await callback.message.edit_text(
                "Pilih preset" + footer(draft),
                reply_markup=strategy_preset_keyboard(),
            )
    elif prev == "prop":
        await wizard_steps.show_prop(callback.message, draft)
    elif prev == "prop_params":
        if draft.prop_pack and draft.prop_pack not in ("none", "generic", "templates"):
            title = f"Template {code(draft.prop_pack)}"
        elif draft.prop_pack == "generic":
            title = bold("Custom prop")
        else:
            title = "Generic params"
        await callback.message.edit_text(
            _prop_params_body(draft, title),
            reply_markup=_prop_params_markup(draft),
        )
    elif prev == "balance":
        await callback.message.edit_text(
            bold("Step 8 — Balance") + footer(draft),
            reply_markup=balance_keyboard(),
        )
    elif prev == "review":
        await _show_review(callback.message, state, draft)
    else:
        await callback.answer(f"Back to {prev} — use Cancel for home", show_alert=True)
        return
    await callback.answer()
