"""Telegram bot entry."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.handlers import admin, home, jobs, presets, wizard
from bot.menu import register_user_commands
from bot.middleware import ContextMiddleware
from bot.notifier import notifier_loop
from bot.settings import Settings
from storage.db import Database, init_db

logging.basicConfig(level=logging.INFO)


async def main_async() -> None:
    settings = Settings()
    if not settings.bot_token:
        logging.error("Set BOT_TOKEN in environment")
        sys.exit(1)
    db_path = Path(settings.db_path) if settings.db_path else None
    await init_db(db_path)
    db = Database(db_path)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await register_user_commands(bot)
    dp = Dispatcher()
    dp.message.middleware(ContextMiddleware(db, settings))
    dp.callback_query.middleware(ContextMiddleware(db, settings))

    dp.include_router(home.router)
    dp.include_router(wizard.router)
    dp.include_router(presets.router)
    dp.include_router(jobs.router)
    dp.include_router(admin.router)

    asyncio.create_task(notifier_loop(bot, db))
    await dp.start_polling(bot)


def main() -> int:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
