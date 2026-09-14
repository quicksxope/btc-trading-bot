"""Poll finished jobs and notify Telegram chats."""

from __future__ import annotations

import asyncio
import json

from aiogram import Bot

from bot.handlers.home import deliver_job_results
from storage.db import Database


async def notifier_loop(bot: Bot, db: Database, interval: float = 3.0) -> None:
    notified: set[str] = set()
    while True:
        async with db.session() as conn:
            cur = await conn.execute(
                """
                SELECT id FROM jobs
                WHERE status IN ('done', 'failed') AND notify_on_done=1
                """
            )
            rows = await cur.fetchall()
        for row in rows:
            jid = row["id"]
            if jid in notified:
                continue
            job = await db.get_job(jid)
            if not job:
                continue
            if job["status"] == "done":
                await deliver_job_results(bot, db, jid)
            elif job["status"] == "failed" and job.get("chat_id"):
                await bot.send_message(
                    job["chat_id"],
                    f"Job `{jid}` failed:\n{job.get('error_message')}",
                )
            async with db.session() as conn:
                await conn.execute(
                    "UPDATE jobs SET notify_on_done=0 WHERE id=?", (jid,)
                )
                await conn.commit()
            notified.add(jid)
        await asyncio.sleep(interval)
