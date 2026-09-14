"""Trading session presets (UTC v0)."""

from __future__ import annotations

from datetime import datetime, time, timezone

from engine.models import SessionId

# Fixed UTC windows (v0)
SESSION_WINDOWS: dict[SessionId, tuple[time, time] | None] = {
    SessionId.ASIA: (time(0, 0), time(8, 0)),
    SessionId.LONDON: (time(7, 0), time(16, 0)),
    SessionId.NY: (time(12, 0), time(21, 0)),
    SessionId.ALL_DAY: None,
}


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_in_session(ts: datetime, session_id: SessionId) -> bool:
    window = SESSION_WINDOWS.get(session_id)
    if window is None:
        return True
    start, end = window
    t = _to_utc(ts).time()
    if start <= end:
        return start <= t < end
    return t >= start or t < end


def session_day_key(ts: datetime, session_id: SessionId) -> str:
    """Accounting day id; rolls at session start for non-all_day."""
    utc = _to_utc(ts)
    if session_id == SessionId.ALL_DAY:
        return utc.strftime("%Y-%m-%d")
    window = SESSION_WINDOWS[session_id]
    assert window is not None
    start, _ = window
    day = utc.date()
    if utc.time() < start:
        from datetime import timedelta

        day = day - timedelta(days=1)
    return f"{session_id.value}:{day.isoformat()}"
