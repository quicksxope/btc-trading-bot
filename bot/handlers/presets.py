"""Run saved presets."""

from __future__ import annotations

import uuid

import yaml
from aiogram import F, Router
from aiogram.types import CallbackQuery

from storage.db import Database
from storage.templates import job_card

router = Router()


@router.callback_query(F.data.startswith("preset:run:"))
async def run_preset(callback: CallbackQuery, db: Database) -> None:
    name = callback.data.split(":", 2)[-1]
    yaml_text = await db.get_preset(callback.from_user.id, name)
    if not yaml_text:
        await callback.answer("Preset not found", show_alert=True)
        return
    running, queued = await db.count_active(callback.from_user.id)
    if running + queued >= 3:
        await callback.answer("Queue full", show_alert=True)
        return
    job_id = uuid.uuid4().hex[:8]
    await db.create_job(job_id, callback.from_user.id, yaml_text, chat_id=callback.message.chat.id)
    pos = await db.queue_position(job_id)
    await callback.message.edit_text(job_card(job_id, "queued", pos))
    await callback.answer()
