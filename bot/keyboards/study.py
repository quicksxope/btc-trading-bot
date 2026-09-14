"""Keyboards for indicator study wizard."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.wizard import nav_row
from engine.catalog import indicator_ids


def study_pool_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    sel = {s.upper() for s in selected}
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for ind in indicator_ids():
        mark = "✓ " if ind in sel else ""
        row.append(
            InlineKeyboardButton(
                text=f"{mark}{ind}",
                callback_data=f"wiz:study:toggle:{ind}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [InlineKeyboardButton(text="Load last pool", callback_data="wiz:study:load_last")]
    )
    rows.append([InlineKeyboardButton(text="Continue »", callback_data="wiz:study:done")])
    rows.append(nav_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)
