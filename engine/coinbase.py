"""
Fetch OHLCV from Coinbase Exchange (public, no API key).

Same model as typical btc-trading-backtest flows:
GET /products/{product_id}/candles — max 300 bars per call, paginate backward.

Docs: https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getproductcandles
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yaml

try:
    import certifi
except ImportError:
    certifi = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "ohlcv"
CATALOG_PATH = ROOT / "configs" / "data_catalog.yaml"

# Legacy Exchange API (still works on many networks)
EXCHANGE_BASE = "https://api.exchange.coinbase.com"
# Advanced Trade public market candles
BROKERAGE_BASE = "https://api.coinbase.com/api/v3/brokerage/market"

GRANULARITY_SEC = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 21600,
    "1d": 86400,
}

BROKERAGE_GRANULARITY = {
    "1m": "ONE_MINUTE",
    "5m": "FIVE_MINUTE",
    "15m": "FIFTEEN_MINUTE",
    "1h": "ONE_HOUR",
    "4h": "FOUR_HOUR",
    "1d": "ONE_DAY",
}

DEFAULT_PRODUCTS = ("BTC-USD", "ETH-USD")
DEFAULT_TIMEFRAMES = ("15m", "1h", "4h", "1d")

PRODUCT_START = {
    "BTC-USD": datetime(2015, 1, 1, tzinfo=timezone.utc),
    "ETH-USD": datetime(2016, 1, 1, tzinfo=timezone.utc),
}

INSTRUMENT_BY_PRODUCT = {
    "BTC-USD": "BTC_PERP",
    "ETH-USD": "ETH_PERP",
}

CHUNK_BARS = 300


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if certifi:
        ctx.load_verify_locations(certifi.where())
    # Telkomsel / captive portals MITM HTTPS — only for local sync (public read-only API)
    if os.environ.get("COINBASE_SSL_VERIFY", "1").lower() in ("0", "false", "no"):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _get_json(url: str, params: dict | None = None) -> dict | list:
    qs = urllib.parse.urlencode(params or {})
    full = url if not qs else f"{url}?{qs}"
    req = urllib.request.Request(
        full,
        headers={
            "User-Agent": "agnostic-trading-backtest/0.1",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as resp:
        return json.loads(resp.read().decode())


def _api_mode() -> str:
    # Default: Exchange API (free historical, no auth) — usual Coinbase backtest source
    return os.environ.get("COINBASE_CANDLES_API", "exchange").lower()


def _fetch_exchange_chunk(product_id: str, gran_sec: int, start: datetime, end: datetime) -> list:
    url = f"{EXCHANGE_BASE}/products/{product_id}/candles"
    params = {
        "granularity": gran_sec,
        "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    batch = _get_json(url, params)
    return batch if isinstance(batch, list) else []


def _fetch_brokerage_chunk(
    product_id: str, timeframe: str, start: datetime, end: datetime
) -> list[dict]:
    gran = BROKERAGE_GRANULARITY[timeframe]
    url = f"{BROKERAGE_BASE}/products/{product_id}/candles"
    params = {
        "granularity": gran,
        "start": str(int(start.timestamp())),
        "end": str(int(end.timestamp())),
    }
    data = _get_json(url, params)
    if isinstance(data, dict):
        return data.get("candles") or []
    return []


def fetch_candles(
    product_id: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    *,
    sleep_sec: float = 0.34,
) -> pd.DataFrame:
    if timeframe not in GRANULARITY_SEC:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    gran = GRANULARITY_SEC[timeframe]
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    mode = _api_mode()
    rows: list = []
    chunk_end = end

    while chunk_end > start:
        chunk_start = max(start, chunk_end - timedelta(seconds=gran * CHUNK_BARS))
        try:
            if mode == "exchange":
                batch = _fetch_exchange_chunk(product_id, gran, chunk_start, chunk_end)
            else:
                batch = _fetch_brokerage_chunk(product_id, timeframe, chunk_start, chunk_end)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2.0)
                continue
            raise

        if not batch:
            chunk_end = chunk_start
            time.sleep(sleep_sec)
            continue

        if mode == "exchange":
            rows.extend(batch)
            oldest = min(c[0] for c in batch)
            chunk_end = datetime.fromtimestamp(oldest, tz=timezone.utc) - timedelta(seconds=gran)
        else:
            rows.extend(batch)
            starts = [int(c["start"]) for c in batch if "start" in c]
            if not starts:
                chunk_end = chunk_start
            else:
                oldest = min(starts)
                chunk_end = datetime.fromtimestamp(oldest, tz=timezone.utc) - timedelta(seconds=gran)
        time.sleep(sleep_sec)

    if not rows:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    if mode == "exchange" or (rows and isinstance(rows[0], list)):
        df = pd.DataFrame(rows, columns=["ts", "low", "high", "open", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["ts"], unit="s", utc=True).dt.tz_localize(None)
        df = df.drop(columns=["ts"])
    else:
        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["start"].astype(int), unit="s", utc=True).dt.tz_localize(
            None
        )
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]

    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    t0 = pd.Timestamp(start.replace(tzinfo=None))
    t1 = pd.Timestamp(end.replace(tzinfo=None))
    return df.loc[(df["timestamp"] >= t0) & (df["timestamp"] <= t1)].reset_index(drop=True)


def write_bars(product_id: str, timeframe: str, df: pd.DataFrame) -> Path:
    out = DATA_ROOT / product_id / f"{timeframe}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return out


def sync_product(
    product_id: str,
    timeframes: tuple[str, ...] = DEFAULT_TIMEFRAMES,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, Path]:
    start = start or PRODUCT_START.get(product_id, datetime(2018, 1, 1, tzinfo=timezone.utc))
    end = end or datetime.now(timezone.utc)
    paths: dict[str, Path] = {}
    for tf in timeframes:
        print(f"Coinbase: {product_id} {tf} ({_api_mode()}) …", flush=True)
        df = fetch_candles(product_id, tf, start, end)
        paths[tf] = write_bars(product_id, tf, df)
        print(f"  → {len(df)} bars", flush=True)
    return paths


def update_catalog_for_product(product_id: str, timeframes: tuple[str, ...] = DEFAULT_TIMEFRAMES) -> None:
    cat = yaml.safe_load(CATALOG_PATH.read_text()) if CATALOG_PATH.exists() else {"instruments": {}}
    instruments = cat.setdefault("instruments", {})
    inst_id = INSTRUMENT_BY_PRODUCT.get(product_id, product_id)
    primary = DATA_ROOT / product_id / "15m.csv"
    if not primary.exists():
        primary = DATA_ROOT / product_id / "1h.csv"
    if primary.exists():
        df = pd.read_csv(primary, parse_dates=["timestamp"])
        d0 = df["timestamp"].min().date().isoformat()
        d1 = df["timestamp"].max().date().isoformat()
    else:
        d0, d1 = "unknown", "unknown"
    instruments[inst_id] = {
        "data_symbol": product_id,
        "source": "coinbase",
        "available_from": d0,
        "available_to": d1,
        "timeframes": list(timeframes),
    }
    CATALOG_PATH.write_text(yaml.safe_dump(cat, sort_keys=False))


def sync_all(
    products: tuple[str, ...] = DEFAULT_PRODUCTS,
    timeframes: tuple[str, ...] = DEFAULT_TIMEFRAMES,
) -> None:
    for product in products:
        sync_product(product, timeframes=timeframes)
        update_catalog_for_product(product, timeframes=timeframes)
