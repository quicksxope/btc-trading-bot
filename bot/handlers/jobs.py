"""Re-run and compare job actions."""

from __future__ import annotations

import json
import uuid

from aiogram import F, Router
from aiogram.types import CallbackQuery

from engine.models import BacktestResult
from storage.db import Database
from storage.templates import compare_block, job_card

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
    prev = await db.last_done_job(callback.from_user.id)
    if not prev or prev["id"] == current_id:
        await callback.answer("No previous run", show_alert=True)
        return
    cur_r = BacktestResult.model_validate(json.loads(current["result_json"]))
    prev_r = BacktestResult.model_validate(json.loads(prev["result_json"]))
    text = compare_block(
        prev["id"],
        cur_r.net_pnl_pct - prev_r.net_pnl_pct,
        cur_r.max_drawdown_pct - prev_r.max_drawdown_pct,
    )
    await callback.message.answer(text)
    await callback.answer()
