"""Telegram HTML formatting (avoids Markdown underscore bugs)."""

from __future__ import annotations

from html import escape

from bot.fsm.validation import BacktestDraft


def footer(draft: BacktestDraft) -> str:
    return f"\n\n<code>{escape(draft.mini_spec_footer())}</code>"


def bold(text: str) -> str:
    return f"<b>{escape(text)}</b>"


def code(text: str) -> str:
    return f"<code>{escape(text)}</code>"


def pre(text: str) -> str:
    return f"<pre>{escape(text)}</pre>"
