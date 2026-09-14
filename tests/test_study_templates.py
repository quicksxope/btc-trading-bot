from storage.study_templates import study_result_summary


def test_study_summary_includes_trade_count():
    payload = {
        "indicator_pool": ["RSI"],
        "mix_count": 1,
        "pass_count": 1,
        "best_mix_label": "RSI",
        "best": {
            "net_pnl_pct": 4.5,
            "max_drawdown_pct": 2,
            "win_rate": 55,
            "trade_count": 17,
            "profit_factor": 1.2,
            "prop_pass": True,
            "trading_days": 4,
        },
        "rows": [
            {
                "rank": 1,
                "mix_label": "RSI",
                "signal_bars_long": 100,
                "signal_bars_short": 80,
                "result": {
                    "net_pnl_pct": 4.5,
                    "max_drawdown_pct": 2,
                    "win_rate": 55,
                    "trade_count": 17,
                    "profit_factor": 1.2,
                    "prop_pass": True,
                },
            }
        ],
    }
    text = study_result_summary("abc123", payload, "BTC_PERP", "30m")
    assert "17 trades" in text
    assert "4.50%" in text
    assert "sig L100/S80" in text
