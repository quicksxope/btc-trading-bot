"""USD prop engine (Phase B)."""

import pandas as pd

from engine.models import PropFirmConfig
from engine.prop_usd import (
    PropUsdSpec,
    check_consistency_topstep,
    evaluate_equity_usd_breaches,
    evaluate_prop_usd,
    max_loss_floor,
)


def test_static_max_loss_floor():
    spec = PropUsdSpec(
        pack_id="t",
        initial_balance_usd=50000,
        daily_loss_limit_usd=1500,
        max_loss_limit_usd=3000,
        max_loss_mode="static",
    )
    assert max_loss_floor(spec, 52000) == 47000


def test_trailing_max_loss_floor_lock():
    spec = PropUsdSpec(
        pack_id="t",
        initial_balance_usd=50000,
        daily_loss_limit_usd=1000,
        max_loss_limit_usd=2000,
        max_loss_mode="trailing_eod",
        mll_lock_at_initial=True,
    )
    assert max_loss_floor(spec, 55000) == 50000


def test_daily_loss_breach():
    spec = PropUsdSpec(
        pack_id="t",
        initial_balance_usd=10000,
        daily_loss_limit_usd=300,
        max_loss_limit_usd=600,
        max_loss_mode="static",
    )
    eq = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="h"),
            "equity": [10000.0, 9950.0, 9680.0],
        }
    )
    ok, reason, _ = evaluate_equity_usd_breaches(eq, spec)
    assert not ok
    assert reason and "DAILY_LOSS" in reason


def test_topstep_consistency():
    daily = pd.Series({"2024-01-01": 2000.0, "2024-01-02": 500.0})
    ok, msg = check_consistency_topstep(daily, profit_target=3000, ratio=0.5)
    assert not ok
    assert "FAIL" in msg


def test_evaluate_prop_usd_pass_target():
    prop = PropFirmConfig(enabled=True, pack_id="holaprime_1step_50k")
    eq = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="D"),
            "equity": [50000, 51000, 52000, 53000, 56000],
        }
    )
    trades = pd.DataFrame(
        {
            "exit_time": pd.to_datetime(["2024-01-02", "2024-01-04"]),
            "pnl": [1000.0, 4000.0],
        }
    )
    state = evaluate_prop_usd(prop, eq, trades, 50000)
    assert state.pass_prop
