# Coinbase historical data

## Source

**Coinbase Exchange REST** — public candles, no API key:

- Base: `https://api.exchange.coinbase.com`
- Endpoint: `GET /products/{product_id}/candles`
- Products: `BTC-USD`, `ETH-USD`
- Granularity (seconds): 60, 300, 900, 3600, 21600, 86400 → mapped to `1m` … `1d`
- **Max 300 candles** per request → script walks backward in time

Official reference: [Get product candles](https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getproductcandles)

Response row: `[ time, low, high, open, close, volume ]` (time = Unix UTC).

## Sync locally / VPS

```bash
python scripts/fetch_coinbase.py
# one product:
python scripts/fetch_coinbase.py --product BTC-USD --timeframe 1h
backtest sync-coinbase
```

Output: `data/ohlcv/BTC-USD/15m.csv` (and `1h`, `4h`, `1d`).

## Cloud Agent / GitHub

If your [Cloud Agent](https://cursor.com/agents) or [quicksxope/btc-trading-backtest](https://github.com/quicksxope/btc-trading-backtest) had a different fetch script, paste that file here — we can diff and merge. The repo on GitHub is still empty; this project uses the Exchange pagination pattern above by default.

Optional: `COINBASE_CANDLES_API=brokerage` for Advanced Trade market candles (different host/format).
