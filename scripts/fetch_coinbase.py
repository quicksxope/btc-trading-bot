#!/usr/bin/env python3
"""
Download BTC-USD / ETH-USD OHLCV from Coinbase Exchange (free public candles).

See docs/DATA_COINBASE.md and:
https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getproductcandles
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.coinbase import DEFAULT_PRODUCTS, DEFAULT_TIMEFRAMES, sync_all, sync_product


def probe() -> int:
    import ssl
    import urllib.request

    from engine.coinbase import EXCHANGE_BASE, _ssl_context

    url = f"{EXCHANGE_BASE}/products/ETH-USD/ticker"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "backtest-probe/1"}),
            timeout=20,
            context=_ssl_context(),
        ) as r:
            body = r.read()
        print(f"OK — HTTP 200, {len(body)} bytes from Coinbase Exchange")
        if body:
            print(body[:120].decode(errors="replace"))
        else:
            print(
                "WARNING: empty body — ISP often blocks crypto APIs (Telkomsel/internet positif). "
                "Try VPN / WiFi lain, atau sync di VPS lalu copy folder data/ohlcv/."
            )
        return 0 if body else 2
    except ssl.SSLError as e:
        print(f"SSL error: {e}")
        print("Coba: COINBASE_SSL_VERIFY=0 python scripts/fetch_coinbase.py --probe")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def main() -> int:
    p = argparse.ArgumentParser(description="Sync Coinbase Exchange candle history")
    p.add_argument("--probe", action="store_true", help="Test Coinbase connectivity only")
    p.add_argument("--product", action="append", help="e.g. BTC-USD (default: both BTC and ETH)")
    p.add_argument("--timeframe", action="append", help="e.g. 15m (default: 15m 1h 4h 1d)")
    args = p.parse_args()
    if args.probe:
        return probe()
    products = tuple(args.product) if args.product else DEFAULT_PRODUCTS
    tfs = tuple(args.timeframe) if args.timeframe else DEFAULT_TIMEFRAMES
    if len(products) == 1 and args.product:
        sync_product(products[0], timeframes=tfs)
        from engine.coinbase import update_catalog_for_product

        update_catalog_for_product(products[0], timeframes=tfs)
    else:
        sync_all(products=products, timeframes=tfs)
    print("Done. Catalog updated at configs/data_catalog.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
