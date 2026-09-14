"""Prop firm template packs."""

from engine.prop_firm import load_prop_pack, merge_prop_config
from engine.models import PropFirmConfig


def test_hola_1step_50k_pack():
    p = load_prop_pack("holaprime_1step_50k")
    assert p.initial_balance_usd == 50000
    assert p.profit_target_pct == 10.0
    assert p.reference_usd["profit_target"] == 5000


def test_topstep_50k_pack():
    p = load_prop_pack("topstep_50k_combine")
    assert p.profit_target_pct == 6.0
    assert p.max_drawdown_pct == 4.0
    assert p.reference_usd["max_loss"] == 2000


def test_merge_keeps_overrides():
    cfg = PropFirmConfig(
        pack_id="topstep_50k_combine",
        daily_loss_pct=2.5,
        max_drawdown_pct=4.0,
    )
    merged = merge_prop_config(cfg)
    assert merged.daily_loss_pct == 2.5
    assert merged.profit_target_pct == 6.0
