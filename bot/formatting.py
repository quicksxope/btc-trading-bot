"""Telegram HTML formatting (avoids Markdown underscore bugs)."""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.fsm.validation import BacktestDraft

TELEGRAM_MESSAGE_LIMIT = 4096


def footer(draft: BacktestDraft) -> str:
    return f"\n\n<code>{escape(draft.mini_spec_footer())}</code>"


def bold(text: str) -> str:
    return f"<b>{escape(text)}</b>"


def code(text: str) -> str:
    return f"<code>{escape(text)}</code>"


def pre(text: str) -> str:
    return f"<pre>{escape(text)}</pre>"


def fit_telegram_html(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> str:
    """Clip HTML text to Telegram's message size without mid-tag chaos when possible."""
    if len(text) <= limit:
        return text
    suffix = "\n<i>…truncated</i>"
    budget = max(0, limit - len(suffix))
    cut = text[:budget]
    nl = cut.rfind("\n")
    if nl > budget // 2:
        cut = cut[:nl]
    return cut + suffix
