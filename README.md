# Agnostic Trading Backtest

Single-asset backtest engine (crypto perpetual + CFD macro) with multi-timeframe indicators, session filters (Asia/London/NY), prop-firm rules, Telegram wizard UI, and SQLite job queue for VPS deployment.

## Features

- Instruments: `BTC_PERP`, `ETH_PERP`, `SPX500_CFD`, `NASDAQ_CFD`, `XAUUSD_CFD`
- Execution default: `next_bar_open`
- Telegram bot: full wizard, presets, job queue, CSV/chart delivery
- CLI: reproducible YAML configs

## Setup

```bash
cd agnostic-trading-backtest
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/generate_sample_data.py   # CFD demo only

# Crypto: Coinbase Exchange history (free, public)
python scripts/fetch_coinbase.py
# or: backtest sync-coinbase
```

Copy `.env.example` to `.env` and set `BOT_TOKEN` and optional `ALLOWLIST_TELEGRAM_IDS`.

**Crypto OHLCV** is synced from Coinbase public candles (`BTC-USD`, `ETH-USD`) into `data/ohlcv/`. Bot labels stay `BTC_PERP` / `ETH_PERP`; prices are **Coinbase spot** (same series you used before).

If fetch fails with SSL on your network, run sync on a VPS (`python scripts/fetch_coinbase.py`) or set `COINBASE_CANDLES_API=exchange` to use the legacy Exchange host.

## Run

```bash
# CLI
backtest run -c configs/examples/eth_london.yaml -o /tmp/out

# Worker (VPS)
backtest-worker

# Bot
backtest-bot
```

## Layout

- `engine/` — backtest core
- `bot/` — Telegram FSM wizard
- `worker/` — queue consumer
- `storage/` — SQLite schema, templates
- `configs/` — instruments, prop packs, data catalog
- `jobs/` — per-job artifacts

## Data

Place OHLCV CSV under `data/ohlcv/{symbol}/{timeframe}.csv` with columns `timestamp,open,high,low,close,volume`. Update `configs/data_catalog.yaml` for bot display.
