"""Job queue worker — polls SQLite queue and runs backtests."""

from __future__ import annotations

import asyncio
import logging
import sys

import yaml

from engine.backtest import run_backtest
from engine.models import BacktestConfig
from engine.report import write_artifacts
from storage.db import Database, init_db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("worker")

POLL_SECONDS = 2.0


async def process_job(db: Database, job_id: str) -> None:
    job = await db.get_job(job_id)
    if not job:
        return
    folder = await db.job_folder(job_id)
    config_path = folder / "config.yaml"
    config_path.write_text(job["config_yaml"])
    config = BacktestConfig.model_validate(yaml.safe_load(job["config_yaml"]))

    loop = asyncio.get_running_loop()

    async def progress(stage: str, pct: float) -> None:
        await db.update_job_progress(job_id, stage, pct)

    def on_progress(stage: str, pct: float) -> None:
        asyncio.run_coroutine_threadsafe(progress(stage, pct), loop)

    try:
        result, equity, trades, daily, breach = await asyncio.to_thread(
            run_backtest, config, on_progress
        )
        await progress("Prop evaluation", 95)
        paths = write_artifacts(folder, config, result, equity, trades, daily, breach)
        for kind, path in paths.items():
            await db.register_artifact(job_id, kind, str(path))
        await db.finish_job(job_id, result.model_dump())
        log.info("Job %s done: %.2f%%", job_id, result.net_pnl_pct)
    except Exception as e:
        log.exception("Job %s failed", job_id)
        await db.finish_job(job_id, None, str(e))


async def worker_loop(db: Database) -> None:
    while True:
        job_id = await db.pop_next_job()
        if job_id:
            await process_job(db, job_id)
        else:
            await asyncio.sleep(POLL_SECONDS)


def main() -> int:
    async def _run() -> None:
        await init_db()
        db = Database()
        log.info("Worker started")
        await worker_loop(db)

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
