"""Async SQLite access."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "app.db"
SCHEMA = Path(__file__).resolve().parent / "schema.sql"
JOBS_ROOT = ROOT / "jobs"


async def init_db(db_path: Path | None = None) -> Path:
    path = db_path or DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    JOBS_ROOT.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as db:
        await db.executescript(SCHEMA.read_text())
        await db.commit()
    return path


class Database:
    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_DB

    @asynccontextmanager
    async def session(self):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            yield db

    async def ensure_user(self, telegram_id: int, username: str | None = None) -> None:
        async with self.session() as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)",
                (telegram_id, username),
            )
            await db.commit()

    async def save_preset(self, telegram_id: int, name: str, config_yaml: str) -> None:
        async with self.session() as db:
            await db.execute(
                """
                INSERT INTO presets (telegram_id, name, config_yaml) VALUES (?, ?, ?)
                ON CONFLICT(telegram_id, name) DO UPDATE SET config_yaml=excluded.config_yaml
                """,
                (telegram_id, name, config_yaml),
            )
            await db.commit()

    async def list_presets(self, telegram_id: int) -> list[dict]:
        async with self.session() as db:
            cur = await db.execute(
                "SELECT id, name, created_at FROM presets WHERE telegram_id=? ORDER BY name",
                (telegram_id,),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get_preset(self, telegram_id: int, name: str) -> str | None:
        async with self.session() as db:
            cur = await db.execute(
                "SELECT config_yaml FROM presets WHERE telegram_id=? AND name=?",
                (telegram_id, name),
            )
            row = await cur.fetchone()
            return row["config_yaml"] if row else None

    async def create_job(
        self,
        job_id: str,
        telegram_id: int,
        config_yaml: str,
        chat_id: int | None = None,
        compare_job_id: str | None = None,
    ) -> None:
        async with self.session() as db:
            await db.execute(
                """
                INSERT INTO jobs (id, telegram_id, config_yaml, chat_id, compare_job_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, telegram_id, config_yaml, chat_id, compare_job_id),
            )
            await db.execute("INSERT INTO job_queue (job_id) VALUES (?)", (job_id,))
            await db.commit()

    async def queue_position(self, job_id: str) -> int | None:
        async with self.session() as db:
            cur = await db.execute("SELECT seq FROM job_queue WHERE job_id=?", (job_id,))
            row = await cur.fetchone()
            if not row:
                return None
            cur2 = await db.execute(
                "SELECT COUNT(*) AS c FROM job_queue WHERE seq <= ?",
                (row["seq"],),
            )
            r2 = await cur2.fetchone()
            return int(r2["c"]) if r2 else None

    async def pop_next_job(self) -> str | None:
        async with self.session() as db:
            cur = await db.execute(
                "SELECT job_id FROM job_queue ORDER BY seq ASC LIMIT 1"
            )
            row = await cur.fetchone()
            if not row:
                return None
            job_id = row["job_id"]
            await db.execute("DELETE FROM job_queue WHERE job_id=?", (job_id,))
            await db.execute(
                "UPDATE jobs SET status='running', started_at=datetime('now') WHERE id=?",
                (job_id,),
            )
            await db.commit()
            return job_id

    async def update_job_progress(
        self,
        job_id: str,
        stage: str,
        pct: float,
        message_id: int | None = None,
    ) -> None:
        async with self.session() as db:
            await db.execute(
                """
                UPDATE jobs SET progress_stage=?, progress_pct=?, progress_message_id=COALESCE(?, progress_message_id)
                WHERE id=?
                """,
                (stage, pct, message_id, job_id),
            )
            await db.commit()

    async def finish_job(
        self,
        job_id: str,
        result: dict | None,
        error: str | None = None,
    ) -> None:
        async with self.session() as db:
            await db.execute(
                """
                UPDATE jobs SET status=?, result_json=?, error_message=?,
                finished_at=datetime('now'), progress_pct=100, progress_stage='Done'
                WHERE id=?
                """,
                ("failed" if error else "done", json.dumps(result) if result else None, error, job_id),
            )
            await db.commit()

    async def cancel_job(self, job_id: str, telegram_id: int) -> bool:
        async with self.session() as db:
            cur = await db.execute(
                "SELECT status FROM jobs WHERE id=? AND telegram_id=?",
                (job_id, telegram_id),
            )
            row = await cur.fetchone()
            if not row:
                return False
            if row["status"] == "queued":
                await db.execute("DELETE FROM job_queue WHERE job_id=?", (job_id,))
                await db.execute(
                    "UPDATE jobs SET status='cancelled', finished_at=datetime('now') WHERE id=?",
                    (job_id,),
                )
                await db.commit()
                return True
            return False

    async def count_active(self, telegram_id: int) -> tuple[int, int]:
        async with self.session() as db:
            cur = await db.execute(
                """
                SELECT
                  SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) AS running,
                  SUM(CASE WHEN status='queued' THEN 1 ELSE 0 END) AS queued
                FROM jobs WHERE telegram_id=?
                """,
                (telegram_id,),
            )
            row = await cur.fetchone()
            return int(row["running"] or 0), int(row["queued"] or 0)

    async def get_job(self, job_id: str) -> dict | None:
        async with self.session() as db:
            cur = await db.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def last_done_job(self, telegram_id: int) -> dict | None:
        async with self.session() as db:
            cur = await db.execute(
                """
                SELECT * FROM jobs WHERE telegram_id=? AND status='done'
                ORDER BY finished_at DESC LIMIT 1
                """,
                (telegram_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def register_artifact(self, job_id: str, kind: str, path: str) -> None:
        async with self.session() as db:
            await db.execute(
                "INSERT INTO job_artifacts (job_id, kind, path) VALUES (?, ?, ?)",
                (job_id, kind, path),
            )
            await db.commit()

    async def list_artifacts(self, job_id: str) -> list[dict]:
        async with self.session() as db:
            cur = await db.execute(
                "SELECT kind, path FROM job_artifacts WHERE job_id=?",
                (job_id,),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def job_folder(self, job_id: str) -> Path:
        p = JOBS_ROOT / job_id
        p.mkdir(parents=True, exist_ok=True)
        return p


def job_artifact_layout(job_id: str) -> dict[str, Path]:
    base = JOBS_ROOT / job_id
    return {
        "config": base / "config.yaml",
        "equity": base / "equity.csv",
        "trades": base / "trades.csv",
        "daily": base / "daily.csv",
        "chart": base / "equity.png",
        "breach_log": base / "breach_log.txt",
    }
