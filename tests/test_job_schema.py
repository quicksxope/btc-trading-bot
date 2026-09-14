import pytest

from storage.db import Database, init_db, job_artifact_layout


@pytest.mark.asyncio
async def test_create_job_and_queue(tmp_path):
    db_path = tmp_path / "test.db"
    await init_db(db_path)
    db = Database(db_path)
    await db.ensure_user(1, "tester")
    await db.create_job("abc123", 1, "instrument: ETH_PERP\n", chat_id=100)
    pos = await db.queue_position("abc123")
    assert pos == 1
    job_id = await db.pop_next_job()
    assert job_id == "abc123"
    layout = job_artifact_layout("abc123")
    assert layout["equity"].name == "equity.csv"
