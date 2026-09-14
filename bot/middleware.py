"""Inject db and settings; allowlist gate."""

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.settings import Settings
from storage.db import Database


class ContextMiddleware(BaseMiddleware):
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["db"] = self.db
        data["settings"] = self.settings
        from aiogram.types import CallbackQuery, Message

        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        allowed = self.settings.allowed_ids()
        if allowed and user and user.id not in allowed:
            if isinstance(event, CallbackQuery):
                await event.answer("Unauthorized", show_alert=True)
            return None
        return await handler(event, data)
