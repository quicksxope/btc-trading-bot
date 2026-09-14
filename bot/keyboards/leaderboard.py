"""Leaderboard inline keyboard."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from storage.job_rank import job_button_label, sort_jobs_by_score


def leaderboard_keyboard(jobs: list[dict], *, limit: int = 10) -> InlineKeyboardMarkup:
    ranked = sort_jobs_by_score(jobs)[:limit]
    rows = [
        [InlineKeyboardButton(text=job_button_label(j), callback_data=f"job:view:{j['id']}")]
        for j in ranked
    ]
    rows.append([InlineKeyboardButton(text="« Home", callback_data="home:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
