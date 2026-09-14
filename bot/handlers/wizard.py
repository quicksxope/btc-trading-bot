"""Wizard FSM handlers."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, timedelta
from html import escape as html_escape

import yaml
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.fsm.validation import BacktestDraft, ValidationError, draft_to_config
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
            bold("Step 1 — Asset class") + "\nPilih kelas aset." + footer(draft),
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

    data = await state.get_data()
    draft = _load_draft(data)
    draft.asset_class = callback.data.split(":")[-1]  # type: ignore[assignment]
    await state.update_data(**_save_draft(data, draft))
    await push_step(state, "instrument")
    await callback.message.edit_text(
        bold("Step 2 — Instrument") + "\nPilih satu instrument." + footer(draft),
        reply_markup=instrument_keyboard(draft),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:inst:"))
async def pick_instrument(callback: CallbackQuery, state: FSMContext) -> None:
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
    await state.update_data(**_save_draft(data, draft))
    await callback.message.edit_text(
        bold("Step 3 — Date range") + extra + footer(draft),
        reply_markup=date_preset_keyboard(),
    )
    await callback.answer()


def _apply_date_preset(preset: str, draft: BacktestDraft) -> tuple[date, date]:
    from datetime import date as date_cls

    from engine.instruments import catalog_date_bounds

    end = date_cls.today()
    start_default = end - timedelta(days=365)
    if draft.instrument:
        bounds = catalog_date_bounds(draft.instrument)
        if bounds:
            start_default, end = bounds
    if preset == "6mo":
        return max(start_default, end - timedelta(days=180)), end
    if preset == "1y":
        return max(start_default, end - timedelta(days=365)), end
    if preset == "max":
        return start_default, end
    if preset == "2024":
        d0, d1 = date(2024, 1, 1), date(2024, 12, 31)
        return max(start_default, d0), min(end, d1)
    return start_default, end


@router.callback_query(F.data.startswith("wiz:date:"))
async def pick_date(callback: CallbackQuery, state: FSMContext) -> None:
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
    await callback.message.edit_text(
        bold("Step 4 — Session") + "\nEntry at bar close; fill next bar open." + footer(draft),
        reply_markup=session_keyboard(draft),
    )
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
    await state.set_state(WizardStates.active)
    await state.update_data(**_save_draft(data, draft))
    await message.answer(
        bold("Step 4 — Session") + footer(draft),
        reply_markup=session_keyboard(draft),
    )


@router.callback_query(F.data.startswith("wiz:sess:"))
async def pick_session(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    sid = callback.data.split(":")[-1]
    draft.session_id = SessionId(sid)
    if draft.asset_class == "cfd":
        draft.session_trading = True
        draft.session_accounting = True
    await state.update_data(**_save_draft(data, draft))
    await callback.message.edit_text(
        bold("Session toggles") + footer(draft),
        reply_markup=session_toggles_keyboard(draft),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:stoggle:"))
async def session_toggles(callback: CallbackQuery, state: FSMContext) -> None:
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
        await callback.message.edit_text(
            bold("Step 5 — Primary timeframe") + footer(draft),
            reply_markup=primary_tf_keyboard(),
        )
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
    data = await state.get_data()
    draft = _load_draft(data)
    draft.primary_tf = callback.data.split(":")[-1]
    await state.update_data(**_save_draft(data, draft))
    await callback.message.edit_text(
        bold("Context timeframes") + " (multi-select)" + footer(draft),
        reply_markup=context_tf_keyboard(draft.context_tfs),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:ctf:"))
async def pick_context_tf(callback: CallbackQuery, state: FSMContext) -> None:
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


@router.callback_query(F.data == "wiz:str:preset")
async def strategy_preset_mode(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    draft.strategy_mode = "preset"
    await state.update_data(**_save_draft(data, draft))
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
    await push_step(state, "prop")
    hint = ""
    if draft.strategy_preset == "cipher_b":
        hint = "\n<i>Disarankan primary 30m (Coinbase: resample dari 15m).</i>"
    await callback.message.edit_text(
        bold("Step 7 — Prop firm") + hint + footer(draft),
        reply_markup=prop_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:prop:"))
async def pick_prop(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    pack = callback.data.split(":")[-1]
    draft.prop_pack = pack
    if pack == "none":
        await state.update_data(**_save_draft(data, draft))
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
        await callback.message.edit_text(
            "Prop template" + footer(draft),
            reply_markup=prop_template_keyboard(),
        )
        await callback.answer()
        return
    if pack == "custom":
        draft.prop_pack = "generic"
        await state.update_data(**_save_draft(data, draft))
        await callback.message.edit_text(
            bold("Custom prop %") + footer(draft),
            reply_markup=prop_custom_keyboard(),
        )
        await callback.answer()
        return
    if pack == "generic":
        await callback.message.edit_text(
            "Generic params" + footer(draft),
            reply_markup=prop_params_keyboard(),
        )
    else:
        _apply_prop_template(draft, pack)
        await state.update_data(**_save_draft(data, draft))
        await callback.message.edit_text(
            f"Pack {code(pack)} — adjust or Continue" + footer(draft),
            reply_markup=prop_custom_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:prop:load:"))
async def load_prop_template_cb(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    pack_id = callback.data.split(":")[-1]
    draft.prop_pack = pack_id
    _apply_prop_template(draft, pack_id)
    await state.update_data(**_save_draft(data, draft))
    await callback.message.edit_text(
        f"Template {code(pack_id)}" + footer(draft),
        reply_markup=prop_custom_keyboard(),
    )
    await callback.answer()


def _apply_prop_template(draft: BacktestDraft, pack_id: str) -> None:
    pack = load_prop_pack(pack_id)
    draft.prop_daily_loss_pct = pack.daily_loss_pct
    draft.prop_max_dd_pct = pack.max_drawdown_pct
    draft.prop_profit_target_pct = pack.profit_target_pct
    draft.prop_min_trading_days = pack.min_trading_days


@router.callback_query(F.data.startswith("wiz:propp:"))
async def prop_params(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft = _load_draft(data)
    p = callback.data.split(":")[-1]
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
        await state.update_data(**_save_draft(data, draft))
        await callback.message.edit_text(
            bold("Step 8 — Balance") + footer(draft),
            reply_markup=balance_keyboard(),
        )
        await callback.answer()
        return
    await state.update_data(**_save_draft(data, draft))
    await callback.answer("Updated")


@router.callback_query(F.data.startswith("wiz:bal:"))
async def pick_balance(callback: CallbackQuery, state: FSMContext) -> None:
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
    pos = await db.queue_position(job_id)
    await callback.message.edit_text(job_card(job_id, "queued", pos))
    await state.clear()
    await callback.answer("Queued")


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


@router.callback_query(F.data == "wiz:cancel")
async def cancel_wizard(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.clear()
    await show_home(callback.message, callback.from_user.id, db, edit=True)
    await callback.answer()


@router.callback_query(F.data == "wiz:back")
async def wizard_back(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
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
            bold("Step 1 — Asset class") + footer(draft),
            reply_markup=asset_class_keyboard(),
        )
    elif prev == "instrument":
        await callback.message.edit_text(
            bold("Step 2 — Instrument") + footer(draft),
            reply_markup=instrument_keyboard(draft),
        )
    elif prev == "strategy_mode":
        await callback.message.edit_text(
            bold("Step 6 — Strategy") + footer(draft),
            reply_markup=strategy_mode_keyboard(),
        )
    elif prev == "prop":
        await callback.message.edit_text(
            bold("Step 7 — Prop firm") + footer(draft),
            reply_markup=prop_keyboard(),
        )
    else:
        await callback.answer(f"Back to {prev} — use Cancel for home", show_alert=True)
        return
    await callback.answer()
