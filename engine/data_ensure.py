"""On-demand fetch: ensure Supabase has bars for a backtest config."""

from __future__ import annotations

from collections.abc import Callable

from engine.coinbase import fetch_candles
from engine.instruments import load_instrument_profile
from engine.models import AssetClass, BacktestConfig
from engine.supabase_client import is_configured
from engine.warehouse import (
    SOURCE_COINBASE,
    get_coverage,
    missing_segments,
    upsert_bars,
)

ProgressCallback = Callable[[str, float], None]


def _fetch_timeframes(config: BacktestConfig) -> list[str]:
    """Coinbase fetch targets (30m is resampled from 15m)."""
    from engine.data_loader import RESAMPLE_FROM

    raw = [config.timeframes.primary, *config.timeframes.context]
    out: list[str] = []
    for tf in raw:
        src = RESAMPLE_FROM.get(tf, tf)
        if src not in out:
            out.append(src)
    return out


def ensure_bars_for_config(
    config: BacktestConfig,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Fetch missing Coinbase segments into Supabase for this run only."""
    if not is_configured():
        return

    profile = load_instrument_profile(config.instrument)
    if profile.asset_class != AssetClass.CRYPTO_PERP:
        return

    product_id = profile.data_symbol
    tfs = _fetch_timeframes(config)
    u0, u1 = config.date_range.start, config.date_range.end
    total_steps = len(tfs)
    step_i = 0

    for tf in tfs:
        step_i += 1
        base_pct = 5 + (step_i - 1) / total_steps * 25
        if on_progress:
            on_progress(f"Checking DB {product_id} {tf}", base_pct)

        cov = get_coverage(product_id, tf)
        segments = missing_segments(u0, u1, cov)
        if not segments:
            continue

        seg_n = len(segments)
        for si, (start, end) in enumerate(segments):
            if on_progress:
                on_progress(
                    f"Fetching {product_id} {tf} ({si + 1}/{seg_n})",
                    base_pct + (si + 1) / seg_n * (25 / total_steps),
                )
            df = fetch_candles(product_id, tf, start, end)
            upsert_bars(product_id, tf, df, source=SOURCE_COINBASE)

    if on_progress:
        on_progress("Data ready", 30)
