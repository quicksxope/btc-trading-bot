from datetime import date

from engine.backtest import run_backtest
from engine.models import (
    AssetClass,
    BacktestConfig,
    DateRange,
    ExecutionConfig,
    InstrumentId,
    PropFirmConfig,
    SessionConfig,
    SessionId,
    StrategyConfig,
    TimeframeConfig,
)


def test_run_backtest_eth():
    cfg = BacktestConfig(
        instrument=InstrumentId.ETH_PERP,
        asset_class=AssetClass.CRYPTO_PERP,
        date_range=DateRange(start=date(2024, 1, 1), end=date(2024, 2, 1)),
        session=SessionConfig(id=SessionId.ALL_DAY),
        timeframes=TimeframeConfig(primary="15m", context=["1h"]),
        strategy=StrategyConfig(mode="preset", preset="trend_ema_cross"),
        prop_firm=PropFirmConfig(enabled=True, pack_id="generic"),
        execution=ExecutionConfig(initial_balance=100_000),
    )
    result, equity, trades, daily, breach = run_backtest(cfg, skip_ensure=True)
    assert not equity.empty
    assert result.trade_count >= 0
