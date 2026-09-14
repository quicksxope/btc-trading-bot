"""Admin commands: health, queue, data catalog."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.settings import Settings
from engine.instruments import load_data_catalog
from storage.db import Database

router = Router()


def _is_admin(user_id: int, settings: Settings) -> bool:
    allowed = settings.allowed_ids()
    return not allowed or user_id in allowed


@router.message(Command("health"))
async def health(message: Message, settings: Settings) -> None:
    if not _is_admin(message.from_user.id, settings):
        return
    await message.answer("OK — bot and DB reachable")


@router.message(Command("queue"))
async def queue_info(message: Message, db: Database, settings: Settings) -> None:
    if not _is_admin(message.from_user.id, settings):
        return
    running, queued = await db.count_active(message.from_user.id)
    await message.answer(f"Your jobs — running: {running}, queued: {queued}")


@router.message(Command("admin"))
async def data_status(message: Message, settings: Settings) -> None:
    if not _is_admin(message.from_user.id, settings):
        return
    cat = load_data_catalog().get("instruments", {})
    lines = ["<b>Data catalog</b>"]
    for k, v in cat.items():
        src = v.get("source", "local")
        lines.append(
            f"{k} ({src}): {v.get('available_from')} .. {v.get('available_to')} [{v.get('data_symbol')}]"
        )
    await message.answer("\n".join(lines))
