"""Home, status, presets, last results, help."""

from __future__ import annotations

import json

import yaml
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot.formatting import bold, footer
from bot.menu import help_message_html
from bot.review_text import hola_result_disclaimer
from bot.fsm.validation import BacktestDraft
from bot.keyboards import asset_class_keyboard, home_keyboard
from bot.keyboards_leaderboard import leaderboard_keyboard
from engine.models import BacktestResult
from storage import templates
from storage.db import Database
from storage.job_rank import leaderboard_text, rank_among_jobs

router = Router()


async def show_home(
    message: Message,
    telegram_id: int,
    db: Database | None,
    *,
    edit: bool = False,
) -> None:
    running, queued = (0, 0)
    if db:
        running, queued = await db.count_active(telegram_id)
    text = templates.home_status(running == 0 and queued == 0, running, queued)
    if edit:
        await message.edit_text(text, reply_markup=home_keyboard())
    else:
        await message.answer(text, reply_markup=home_keyboard())


@router.message(Command("start"))
async def cmd_start(message: Message, db: Database) -> None:
    await db.ensure_user(message.from_user.id, message.from_user.username)
    await show_home(message, message.from_user.id, db)


@router.message(Command("new"))
async def cmd_new(message: Message, state: FSMContext, db: Database) -> None:
    from bot.states import WizardStates

    await db.ensure_user(message.from_user.id, message.from_user.username)
    await state.clear()
    draft = BacktestDraft()
    await state.update_data(draft=draft.__dict__)
    await state.set_state(WizardStates.active)
    await message.answer(
        bold("Step 1 — Asset class") + "\nPilih kelas aset." + footer(draft),
        reply_markup=asset_class_keyboard(),
    )


@router.callback_query(F.data == "home:study")
async def home_study(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    from bot.states import WizardStates
    from bot.wizard_nav import clear_stack, push_step

    await db.ensure_user(callback.from_user.id, callback.from_user.username)
    await state.clear()
    draft = BacktestDraft(wizard_kind="study")
    last = await db.get_last_indicator_favorite(callback.from_user.id)
    if last:
        draft.study_pool = last[:3]
    await state.update_data(draft=draft.__dict__)
    await state.set_state(WizardStates.active)
    await clear_stack(state)
    await push_step(state, "asset")
    await callback.message.edit_text(
        bold("Indicator study — Step 1 — Asset class") + footer(draft),
        reply_markup=asset_class_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "home:help")
async def help_cb(callback: CallbackQuery) -> None:
    await callback.message.edit_text(help_message_html(), reply_markup=home_keyboard())
    await callback.answer()


@router.callback_query(F.data == "home:status")
async def status_cb(callback: CallbackQuery, db: Database) -> None:
    running, queued = await db.count_active(callback.from_user.id)
    text = (
        f"<b>Status job</b>\n"
        f"Running: {running}\n"
        f"Queued: {queued}\n\n"
        f"Hasil selesai: tombol <b>Last results</b> atau /last"
    )
    await callback.message.edit_text(text, reply_markup=home_keyboard())
    await callback.answer()


@router.callback_query(F.data == "home:last")
async def last_cb(callback: CallbackQuery, db: Database) -> None:
    jobs = await db.list_done_jobs(callback.from_user.id, limit=30)
    if not jobs:
        await callback.answer("No completed runs yet", show_alert=True)
        return
    text = leaderboard_text(jobs, limit=10)
    await callback.message.edit_text(
        text,
        reply_markup=leaderboard_keyboard(jobs, limit=10),
    )
    await callback.answer()


@router.callback_query(F.data == "home:presets")
async def presets_cb(callback: CallbackQuery, db: Database) -> None:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    presets = await db.list_presets(callback.from_user.id)
    if not presets:
        await callback.answer("No presets", show_alert=True)
        return
    rows = [
        [InlineKeyboardButton(text=p["name"], callback_data=f"preset:run:{p['name']}")]
        for p in presets
    ]
    rows.append([InlineKeyboardButton(text="« Home", callback_data="home:back")])
    await callback.message.edit_text(
        "Tap preset to queue run:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(F.data == "home:back")
async def home_back(callback: CallbackQuery, db: Database) -> None:
    await show_home(callback.message, callback.from_user.id, db)
    await callback.answer()


@router.message(Command("presets"))
async def cmd_presets(message: Message, db: Database) -> None:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    presets = await db.list_presets(message.from_user.id)
    if not presets:
        await message.answer("No presets saved.")
        return
    rows = [
        [InlineKeyboardButton(text=p["name"], callback_data=f"preset:run:{p['name']}")]
        for p in presets
    ]
    await message.answer(
        "Presets:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(help_message_html(), reply_markup=home_keyboard())


@router.message(Command("status"))
async def cmd_status(message: Message, db: Database) -> None:
    running, queued = await db.count_active(message.from_user.id)
    text = (
        f"<b>Status job</b>\n"
        f"Running: {running}\n"
        f"Queued: {queued}\n\n"
        f"Hasil selesai: /last"
    )
    await message.answer(text, reply_markup=home_keyboard())


@router.message(Command("last"))
async def cmd_last(message: Message, db: Database) -> None:
    jobs = await db.list_done_jobs(message.from_user.id, limit=30)
    if not jobs:
        await message.answer("No completed runs.")
        return
    text = leaderboard_text(jobs, limit=10)
    await message.answer(text, reply_markup=leaderboard_keyboard(jobs, limit=10))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    await message.answer("Wizard dibatalkan.")
    await show_home(message, message.from_user.id, db)


async def deliver_job_results(bot, db: Database, job_id: str) -> None:
    job = await db.get_job(job_id)
    if not job or job["status"] != "done":
        return
    chat_id = job.get("chat_id")
    if not chat_id:
        return
    raw_result = json.loads(job["result_json"])
    if raw_result.get("kind") == "indicator_study":
        raw_cfg = yaml.safe_load(job["config_yaml"]) if job.get("config_yaml") else {}
        inst = str((raw_cfg or {}).get("instrument", ""))
        primary_tf = ((raw_cfg or {}).get("timeframes") or {}).get("primary", "")
        from storage.study_templates import study_result_summary

        text = study_result_summary(job_id, raw_result, inst, primary_tf or "—")
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Home", callback_data="home:back")],
            ]
        )
        await bot.send_message(chat_id, text, reply_markup=kb)
        return

    result = BacktestResult.model_validate(raw_result)
    compare = None
    if job.get("compare_job_id"):
        prev = await db.get_job(job["compare_job_id"])
        if prev and prev.get("result_json"):
            prev_r = BacktestResult.model_validate(json.loads(prev["result_json"]))
            compare = templates.compare_block(
                job["compare_job_id"],
                result.net_pnl_pct - prev_r.net_pnl_pct,
                result.max_drawdown_pct - prev_r.max_drawdown_pct,
                prev_prop_pass=prev_r.prop_pass,
                cur_prop_pass=result.prop_pass,
                prev_fail_reason=prev_r.prop_fail_reason,
                cur_fail_reason=result.prop_fail_reason,
            )
    raw_cfg = yaml.safe_load(job["config_yaml"]) if job.get("config_yaml") else {}
    prop = (raw_cfg or {}).get("prop_firm") or {}
    pack_id = prop.get("pack_id") if prop.get("enabled") else None
    preset = ((raw_cfg or {}).get("strategy") or {}).get("preset")
    primary_tf = ((raw_cfg or {}).get("timeframes") or {}).get("primary")
    sem_parts = []
    if preset:
        sem_parts.append(f"preset={preset}")
    if primary_tf:
        sem_parts.append(f"tf={primary_tf}")
    if pack_id:
        sem_parts.append(f"prop={pack_id}")
    sem = " | ".join(sem_parts) if sem_parts else job_id[:80]
    footer_note = hola_result_disclaimer(str(pack_id) if pack_id else None)
    recent = await db.list_done_jobs(job["telegram_id"], limit=30)
    rank = rank_among_jobs(job, recent)
    if rank is not None and len(recent) > 1:
        rank_line = f"<i>Leaderboard rank: #{rank} of {min(len(recent), 30)} (PASS first, then PnL).</i>"
        footer_note = f"{rank_line}\n{footer_note}" if footer_note else rank_line
    if preset == "cipher_b" and primary_tf and primary_tf != "30m":
        hint = "<i>Cipher B: 30m recommended (15m resample in DB).</i>"
        footer_note = f"{footer_note}\n{hint}" if footer_note else hint
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Re-run", callback_data=f"job:rerun:{job_id}"),
                InlineKeyboardButton(text="Compare last", callback_data=f"job:compare:{job_id}"),
            ],
            [InlineKeyboardButton(text="« Home", callback_data="home:back")],
        ]
    )
    await bot.send_message(
        chat_id,
        templates.result_summary(job_id, result, sem, compare, footer_note),
        reply_markup=kb,
    )
    arts = await db.list_artifacts(job_id)
    for art in arts:
        if art["kind"] in ("equity", "trades", "daily", "config", "chart"):
            await bot.send_document(chat_id, FSInputFile(art["path"]))
