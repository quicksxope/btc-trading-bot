"""Indicator study helpers."""

from engine.study import indicator_subsets, mix_label, rank_study_rows, strategy_for_mix
from engine.models import BacktestResult


def test_indicator_subsets_three():
    subs = indicator_subsets(["RSI", "WAVETREND", "ADX"])
    assert len(subs) == 7
    assert ("RSI",) in subs
    assert ("ADX", "RSI", "WAVETREND") in subs


def test_mix_label():
    assert mix_label(("RSI", "WAVETREND")) == "RSI+WAVETREND"


def test_strategy_for_mix_and_rules():
    strat = strategy_for_mix(("RSI", "WAVETREND"))
    assert strat.custom_rules_v2
    assert " and " in strat.custom_rules_v2.long_when
    names = {s["name"] for s in strat.custom_indicators}
    assert "RSI" in names and "WAVETREND" in names


def test_strategy_for_mix_bressert_parses():
    from engine.rules import validate_expression

    strat = strategy_for_mix(("BRESSERT", "RSI"))
    assert strat.custom_rules_v2
    validate_expression(strat.custom_rules_v2.long_when)
    validate_expression(strat.custom_rules_v2.short_when)


def test_rank_study_rows_pass_first():
    rows = [
        {
            "mix_label": "A",
            "result": BacktestResult(
                net_pnl_pct=10,
                max_drawdown_pct=1,
                win_rate=50,
                trade_count=5,
                profit_factor=1.2,
                prop_pass=False,
            ).model_dump(),
        },
        {
            "mix_label": "B",
            "result": BacktestResult(
                net_pnl_pct=5,
                max_drawdown_pct=1,
                win_rate=50,
                trade_count=5,
                profit_factor=1.2,
                prop_pass=True,
            ).model_dump(),
        },
    ]
    ranked = rank_study_rows(rows, prop_enabled=True)
    assert ranked[0]["mix_label"] == "B"
    assert ranked[0]["rank"] == 1
