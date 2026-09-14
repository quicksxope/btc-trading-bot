from datetime import date, datetime, timezone

from engine.warehouse import Coverage, missing_segments


def test_missing_segments_no_coverage():
    segs = missing_segments(date(2024, 1, 1), date(2024, 1, 31), None)
    assert len(segs) == 1


def test_missing_segments_fully_covered():
    cov = Coverage(
        product_id="BTC-USD",
        timeframe="15m",
        first_ts=datetime(2023, 1, 1, tzinfo=timezone.utc),
        last_ts=datetime(2025, 1, 1, tzinfo=timezone.utc),
        bar_count=1000,
    )
    segs = missing_segments(date(2024, 6, 1), date(2024, 6, 30), cov)
    assert segs == []


def test_missing_segments_needs_tail():
    cov = Coverage(
        product_id="BTC-USD",
        timeframe="15m",
        first_ts=datetime(2024, 1, 1, tzinfo=timezone.utc),
        last_ts=datetime(2024, 6, 1, tzinfo=timezone.utc),
        bar_count=1000,
    )
    segs = missing_segments(date(2024, 1, 1), date(2024, 12, 31), cov)
    assert len(segs) == 1
