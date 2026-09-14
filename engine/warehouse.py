"""Supabase OHLCV warehouse: coverage, load, upsert."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone

import pandas as pd

from engine.coinbase import GRANULARITY_SEC
from engine.supabase_client import get_client, is_configured

SOURCE_COINBASE = "coinbase_exchange"
UPSERT_BATCH = 400


@dataclass
class Coverage:
    product_id: str
    timeframe: str
    first_ts: datetime | None
    last_ts: datetime | None
    bar_count: int


def _utc_day_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


def _utc_day_end(d: date) -> datetime:
    return datetime.combine(d, time.max, tzinfo=timezone.utc)


def granularity_seconds(timeframe: str) -> int:
    if timeframe not in GRANULARITY_SEC:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    return GRANULARITY_SEC[timeframe]


def missing_segments(
    user_start: date,
    user_end: date,
    cov: Coverage | None,
) -> list[tuple[datetime, datetime]]:
    """UTC ranges to fetch from exchange (inclusive intent)."""
    u0 = _utc_day_start(user_start)
    u1 = _utc_day_end(user_end)
    if cov is None or cov.first_ts is None or cov.last_ts is None or cov.bar_count == 0:
        return [(u0, u1)]

    segments: list[tuple[datetime, datetime]] = []
    first = cov.first_ts if cov.first_ts.tzinfo else cov.first_ts.replace(tzinfo=timezone.utc)
    last = cov.last_ts if cov.last_ts.tzinfo else cov.last_ts.replace(tzinfo=timezone.utc)

    if u0 < first:
        segments.append((u0, first))
    if u1 > last:
        segments.append((last, u1))
    return segments


def get_coverage(product_id: str, timeframe: str) -> Coverage | None:
    if not is_configured():
        return None
    client = get_client()
    res = (
        client.table("ohlcv_coverage")
        .select("*")
        .eq("product_id", product_id)
        .eq("timeframe", timeframe)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return None
    r = rows[0]
    return Coverage(
        product_id=product_id,
        timeframe=timeframe,
        first_ts=_parse_ts(r.get("first_ts")),
        last_ts=_parse_ts(r.get("last_ts")),
        bar_count=int(r.get("bar_count") or 0),
    )


def _parse_ts(v) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    return pd.to_datetime(v, utc=True).to_pydatetime()


def coverage_summary_lines(product_id: str, timeframes: tuple[str, ...] = ("15m", "1h", "4h", "1d")) -> list[str]:
    if not is_configured():
        return ["DB: Supabase not configured (using local CSV)"]
    lines = ["DB warehouse:"]
    for tf in timeframes:
        cov = get_coverage(product_id, tf)
        if not cov or not cov.first_ts:
            lines.append(f"  {tf}: no data yet (fetch on Run)")
        else:
            d0 = cov.first_ts.astimezone(timezone.utc).date()
            d1 = cov.last_ts.astimezone(timezone.utc).date() if cov.last_ts else d0
            lines.append(f"  {tf}: {d0} .. {d1} ({cov.bar_count:,} bars)")
    return lines


def upsert_bars(product_id: str, timeframe: str, df: pd.DataFrame, source: str = SOURCE_COINBASE) -> int:
    if df.empty:
        return 0
    client = get_client()
    records = []
    for _, row in df.iterrows():
        ts = pd.Timestamp(row["timestamp"])
        if ts.tzinfo is None:
            ts = ts.tz_localize(timezone.utc)
        else:
            ts = ts.tz_convert(timezone.utc)
        records.append(
            {
                "product_id": product_id,
                "timeframe": timeframe,
                "ts": ts.isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
                "source": source,
            }
        )
    n = 0
    for i in range(0, len(records), UPSERT_BATCH):
        batch = records[i : i + UPSERT_BATCH]
        client.table("ohlcv_bars").upsert(batch, on_conflict="product_id,timeframe,ts").execute()
        n += len(batch)
    client.rpc(
        "refresh_ohlcv_coverage",
        {"p_product_id": product_id, "p_timeframe": timeframe, "p_source": source},
    ).execute()
    return n


def load_bars_range(
    product_id: str,
    timeframe: str,
    start: date,
    end: date,
    *,
    page_size: int = 1000,
) -> pd.DataFrame:
    client = get_client()
    rows: list[dict] = []
    offset = 0
    t0 = _utc_day_start(start).isoformat()
    t1 = _utc_day_end(end).isoformat()
    while True:
        res = (
            client.table("ohlcv_bars")
            .select("ts, open, high, low, close, volume")
            .eq("product_id", product_id)
            .eq("timeframe", timeframe)
            .gte("ts", t0)
            .lte("ts", t1)
            .order("ts")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = res.data or []
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    if not rows:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows)
    df = df.rename(columns={"ts": "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)
    return df.sort_values("timestamp").reset_index(drop=True)


def warehouse_date_bounds(product_id: str, timeframe: str = "15m") -> tuple[date, date] | None:
    cov = get_coverage(product_id, timeframe)
    if not cov or not cov.first_ts or not cov.last_ts:
        return None
    return (
        cov.first_ts.astimezone(timezone.utc).date(),
        cov.last_ts.astimezone(timezone.utc).date(),
    )
