from datetime import date

import pytest

from bot.fsm.validation import BacktestDraft, ValidationError, draft_to_config, validate_timeframes
from engine.models import InstrumentId, SessionId


def test_timeframe_context_must_be_higher():
    d = BacktestDraft(
        asset_class="crypto_perp",
        instrument=InstrumentId.ETH_PERP,
        primary_tf="1h",
        context_tfs=["15m"],
    )
    with pytest.raises(ValidationError):
        validate_timeframes(d)


def test_draft_to_config_minimal():
    d = BacktestDraft(
        asset_class="crypto_perp",
        instrument=InstrumentId.ETH_PERP,
        date_from=date(2024, 1, 1),
        date_to=date(2024, 3, 1),
        session_id=SessionId.LONDON,
        primary_tf="15m",
        context_tfs=["1h", "4h"],
        strategy_mode="preset",
        strategy_preset="trend_ema_cross",
        prop_pack="generic",
    )
    cfg = draft_to_config(d)
    assert cfg.instrument == InstrumentId.ETH_PERP
    assert cfg.execution.fill == "next_bar_open"


def test_draft_to_config_overrides_risk_reward():
    d = BacktestDraft(
        asset_class="crypto_perp",
        instrument=InstrumentId.BTC_PERP,
        date_from=date(2024, 1, 1),
        date_to=date(2024, 3, 1),
        session_id=SessionId.LONDON,
        primary_tf="15m",
        strategy_mode="preset",
        strategy_preset="trend_ema_cross",
        prop_pack="holaprime_1step_50k",
        prop_daily_loss_pct=3.0,
        prop_max_dd_pct=6.0,
        execution_risk_reward_ratio=3.0,
        initial_balance=50_000.0,
    )
    cfg = draft_to_config(d)
    assert cfg.execution.mode == "sltp_risk"
    assert cfg.execution.risk_reward_ratio == 3.0
