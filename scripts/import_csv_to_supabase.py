#!/usr/bin/env python3
"""Upload local data/ohlcv CSV files into Supabase (one-time migration)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from engine.warehouse import SOURCE_COINBASE, upsert_bars
from engine.supabase_client import is_configured

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "ohlcv"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", required=True, help="e.g. BTC-USD")
    parser.add_argument("--timeframe", action="append", default=["15m", "1h", "4h", "1d"])
    args = parser.parse_args()

    if not is_configured():
        raise SystemExit("Set SUPABASE_URL and SUPABASE_SERVICE_KEY")

    for tf in args.timeframe:
        path = DATA / args.product / f"{tf}.csv"
        if not path.exists():
            print(f"skip missing {path}")
            continue
        df = pd.read_csv(path, parse_dates=["timestamp"])
        n = upsert_bars(args.product, tf, df, source=SOURCE_COINBASE)
        print(f"{args.product} {tf}: {n} rows upserted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
