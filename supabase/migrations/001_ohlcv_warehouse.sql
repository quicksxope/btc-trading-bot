-- Multi-asset, multi-timeframe OHLCV warehouse (Supabase / Postgres)

CREATE TABLE IF NOT EXISTS ohlcv_bars (
  product_id TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  ts TIMESTAMPTZ NOT NULL,
  open DOUBLE PRECISION NOT NULL,
  high DOUBLE PRECISION NOT NULL,
  low DOUBLE PRECISION NOT NULL,
  close DOUBLE PRECISION NOT NULL,
  volume DOUBLE PRECISION NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'coinbase_exchange',
  PRIMARY KEY (product_id, timeframe, ts)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_bars_range
  ON ohlcv_bars (product_id, timeframe, ts);

CREATE TABLE IF NOT EXISTS ohlcv_coverage (
  product_id TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  first_ts TIMESTAMPTZ,
  last_ts TIMESTAMPTZ,
  bar_count BIGINT NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'coinbase_exchange',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (product_id, timeframe)
);

CREATE OR REPLACE FUNCTION refresh_ohlcv_coverage(p_product_id TEXT, p_timeframe TEXT, p_source TEXT DEFAULT 'coinbase_exchange')
RETURNS void
LANGUAGE sql
AS $$
  INSERT INTO ohlcv_coverage (product_id, timeframe, first_ts, last_ts, bar_count, source, updated_at)
  SELECT
    p_product_id,
    p_timeframe,
    min(ts),
    max(ts),
    count(*)::bigint,
    p_source,
    now()
  FROM ohlcv_bars
  WHERE product_id = p_product_id AND timeframe = p_timeframe
  ON CONFLICT (product_id, timeframe) DO UPDATE SET
    first_ts = EXCLUDED.first_ts,
    last_ts = EXCLUDED.last_ts,
    bar_count = EXCLUDED.bar_count,
    source = EXCLUDED.source,
    updated_at = now();
$$;
