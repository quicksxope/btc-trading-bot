"""Re-run and compare job actions."""

from __future__ import annotations

import json
import uuid

import yaml
from aiogram import F, Router
from aiogram.types import CallbackQuery

from engine.models import BacktestResult
from storage.db import Database
from storage.job_rank import job_config_hint, result_from_job
from storage.study_templates import study_result_summary
from storage.templates import compare_block, job_card, result_summary

router = Router()


@router.callback_query(F.data.startswith("job:rerun:"))
async def rerun_job(callback: CallbackQuery, db: Database) -> None:
    old_id = callback.data.split(":")[-1]
    job = await db.get_job(old_id)
    if not job:
        await callback.answer("Job not found", show_alert=True)
        return
    job_id = uuid.uuid4().hex[:8]
    await db.create_job(
        job_id,
        callback.from_user.id,
        job["config_yaml"],
        chat_id=callback.message.chat.id,
    )
    pos = await db.queue_position(job_id)
    await callback.message.answer(job_card(job_id, "queued", pos))
    await callback.answer()


@router.callback_query(F.data.startswith("job:compare:"))
async def compare_job(callback: CallbackQuery, db: Database) -> None:
    current_id = callback.data.split(":")[-1]
    current = await db.get_job(current_id)
    if not current or not current.get("result_json"):
        await callback.answer("No result", show_alert=True)
        return
    prev = await db.previous_done_job(callback.from_user.id, current_id)
    if not prev:
        await callback.answer("No previous run", show_alert=True)
        return
    cur_r = result_from_job(current)
    prev_r = result_from_job(prev)
    if cur_r is None or prev_r is None:
        await callback.answer("Study jobs: open from notification", show_alert=True)
        return
    text = compare_block(
        prev["id"],
        cur_r.net_pnl_pct - prev_r.net_pnl_pct,
        cur_r.max_drawdown_pct - prev_r.max_drawdown_pct,
        prev_prop_pass=prev_r.prop_pass,
        cur_prop_pass=cur_r.prop_pass,
        prev_fail_reason=prev_r.prop_fail_reason,
        cur_fail_reason=cur_r.prop_fail_reason,
    )
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data.startswith("job:view:"))
async def view_job(callback: CallbackQuery, db: Database) -> None:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    job_id = callback.data.split(":")[-1]
    job = await db.get_job(job_id)
    if not job or job.get("telegram_id") != callback.from_user.id:
        await callback.answer("Not found", show_alert=True)
        return
    if job.get("status") != "done" or not job.get("result_json"):
        await callback.answer("Job not finished", show_alert=True)
        return
    raw = json.loads(job["result_json"])
    if raw.get("kind") == "indicator_study":
        cfg = yaml.safe_load(job["config_yaml"]) or {}
        inst = str(cfg.get("instrument", ""))
        tf = (cfg.get("timeframes") or {}).get("primary", "")
        prop = (cfg.get("prop_firm") or {})
        pack_id = prop.get("pack_id") if prop.get("enabled") else None
        text = study_result_summary(job_id, raw, inst, tf or "—", prop_pack_id=pack_id)
        await callback.message.answer(text)
        await callback.answer()
        return
    result = BacktestResult.model_validate(raw)
    sem = job_config_hint(job)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Re-run", callback_data=f"job:rerun:{job_id}"),
                InlineKeyboardButton(text="Compare prev", callback_data=f"job:compare:{job_id}"),
            ],
            [InlineKeyboardButton(text="« Leaderboard", callback_data="home:last")],
        ]
    )
    await callback.message.edit_text(
        result_summary(job_id, result, sem),
        reply_markup=kb,
    )
    await callback.answer()
