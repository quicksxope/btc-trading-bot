"""SL/TP execution helpers."""

import pandas as pd

from engine.execution_sltp import (
    capped_risk_per_trade_usd,
    enrich_execution_from_pack,
    intrabar_exit,
    size_units_for_risk,
    sltp_trade_record,
    swing_stops_long,
)
from engine.models import ExecutionConfig, PropFirmConfig
from engine.execution_sltp import OpenTrade


def test_swing_stops_long():
    lows = pd.Series([100.0, 98.0, 97.0, 99.0, 101.0])
    out = swing_stops_long(lows, 4, 100.0, 3, 2.0)
    assert out is not None
    sl, tp, risk = out
    assert sl == 97.0
    assert tp == 100.0 + 3.0 * 2.0


def test_intrabar_sl_first():
    t = OpenTrade(1, 100.0, 1.0, 98.0, 106.0, entry_time=pd.Timestamp("2024-01-01"))
    hit = intrabar_exit(t, high=107.0, low=97.0)
    assert hit == (98.0, "sl")


def test_size_units_for_risk():
    size = size_units_for_risk(200.0, 10.0, 1.0, 10000.0, 0.99)
    assert abs(size - 20.0) < 1e-6


def test_capped_risk_per_trade_one_tenth_max_loss():
    prop = PropFirmConfig(
        enabled=True,
        pack_id="holaprime_1step_50k",
        daily_loss_pct=3.0,
        max_drawdown_pct=6.0,
    )
    assert capped_risk_per_trade_usd(1000.0, prop, 50_000.0) == 300.0
    assert capped_risk_per_trade_usd(200.0, prop, 50_000.0) == 200.0


def test_sltp_trade_record_fields():
    t = OpenTrade(1, 100.0, 2.0, 98.0, 106.0, entry_time=pd.Timestamp("2024-01-01"))
    rec = sltp_trade_record(
        t,
        exit_time=pd.Timestamp("2024-01-02"),
        exit_price=106.0,
        exit_reason="tp",
        net_pnl=12.0,
        contract_size=1.0,
    )
    assert rec["entry_price"] == 100.0
    assert rec["stop_loss"] == 98.0
    assert rec["take_profit"] == 106.0
    assert rec["risk_usd"] == 4.0
    assert rec["r_multiple"] == 3.0


def test_enrich_from_hola_pack():
    exe = ExecutionConfig(initial_balance=50000)
    merged = enrich_execution_from_pack(exe, "holaprime_1step_50k")
    assert merged.mode == "sltp_risk"
    assert merged.risk_per_trade_usd == 1000
