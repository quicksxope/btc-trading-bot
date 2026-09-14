"""CLI entry: backtest run --config path.yaml"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from engine.backtest import run_backtest
from engine.models import BacktestConfig
from engine.report import write_artifacts


def load_config(path: Path) -> BacktestConfig:
    raw = yaml.safe_load(path.read_text())
    return BacktestConfig.model_validate(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agnostic backtest CLI")
    parser.add_argument("command", choices=["run", "sync-coinbase"], help="Command")
    parser.add_argument("--config", "-c", type=Path, help="Config YAML path (run)")
    parser.add_argument("--out", "-o", type=Path, help="Output directory (run)")
    parser.add_argument("--product", action="append", help="Coinbase product, e.g. BTC-USD")
    args = parser.parse_args(argv)

    if args.command == "run":
        if not args.config or not args.out:
            parser.error("run requires --config and --out")
        config = load_config(args.config)
        result, equity, trades, daily, breach = run_backtest(config)
        write_artifacts(args.out, config, result, equity, trades, daily, breach)
        print(json.dumps(result.model_dump(), indent=2))
        return 0
    if args.command == "sync-coinbase":
        from engine.coinbase import DEFAULT_PRODUCTS, DEFAULT_TIMEFRAMES, sync_all, sync_product
        from engine.coinbase import update_catalog_for_product

        products = tuple(args.product) if args.product else DEFAULT_PRODUCTS
        if len(products) == 1:
            sync_product(products[0])
            update_catalog_for_product(products[0])
        else:
            sync_all(products=products, timeframes=DEFAULT_TIMEFRAMES)
        print("Coinbase sync complete.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
