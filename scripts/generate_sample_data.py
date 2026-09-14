"""Generate synthetic OHLCV for local dev."""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ["BTCUSDT", "ETHUSDT", "US500", "US100", "XAUUSD"]
TF_MINUTES = {"15m": 15, "1h": 60, "4h": 240, "1d": 1440}


def gen(symbol: str, minutes: int, n_bars: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2024-01-01", tz="UTC")
    idx = pd.date_range(start, periods=n_bars, freq=f"{minutes}min")
    ret = rng.normal(0, 0.001, n_bars)
    price = 100 * (1 + ret).cumprod()
    if symbol == "BTCUSDT":
        price *= 400
    elif symbol == "ETHUSDT":
        price *= 25
    elif symbol == "XAUUSD":
        price *= 20
    high = price * (1 + rng.uniform(0, 0.002, n_bars))
    low = price * (1 - rng.uniform(0, 0.002, n_bars))
    open_ = np.roll(price, 1)
    open_[0] = price[0]
    vol = rng.uniform(100, 1000, n_bars)
    return pd.DataFrame(
        {
            "timestamp": idx.tz_localize(None),
            "open": open_,
            "high": high,
            "low": low,
            "close": price,
            "volume": vol,
        }
    )


def main() -> None:
    for sym in SYMBOLS:
        for tf, mins in TF_MINUTES.items():
            n = 5000 if mins <= 60 else 800
            df = gen(sym, mins, n, hash(sym + tf) % 2**31)
            out = ROOT / "data" / "ohlcv" / sym / f"{tf}.csv"
            out.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(out, index=False)
            print("wrote", out)


if __name__ == "__main__":
    main()
