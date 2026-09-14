# Supabase OHLCV warehouse

Shared multi-asset, multi-timeframe bars for backtests. Data is fetched **on Run** (no daily cron).

## Setup

1. Create a Supabase project.
2. Run SQL from `supabase/migrations/001_ohlcv_warehouse.sql` in the SQL editor.
3. On the VPS, set in `.env`:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY` (service role — server only)

## Flow

1. User queues a backtest (Telegram bot → SQLite job).
2. Worker calls `ensure_bars_for_config`: compares job date range + TFs to `ohlcv_coverage`, fetches gaps from Coinbase, upserts `ohlcv_bars`.
3. `load_bars` reads from Supabase; falls back to `data/ohlcv/<symbol>/<tf>.csv` if unset or empty.

## Bot

Instrument step shows `coverage_summary_lines` (15m / 1h / 4h / 1d). Date presets use the intersection of YAML catalog and warehouse bounds when configured.

## Import existing CSV (optional)

Use `scripts/import_csv_to_supabase.py` on the VPS after migration to seed from local `data/ohlcv/`.
