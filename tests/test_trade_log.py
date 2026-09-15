from storage.trade_log import format_trades_html


def test_format_trades_html_sltp_line():
    text = format_trades_html(
        [
            {
                "side": "long",
                "entry_time": "2024-01-01T10:30:00",
                "exit_time": "2024-01-01T12:00:00",
                "entry_price": 95000.0,
                "stop_loss": 94500.0,
                "take_profit": 96000.0,
                "risk_usd": 250.5,
                "pnl": 500.25,
                "exit_reason": "tp",
                "r_multiple": 2.0,
            }
        ],
        limit=5,
    )
    assert "2024-01-01 10:30→2024-01-01 12:00" in text
    assert "SL 94,500.00" in text
    assert "risk $250.50" in text
    assert "$500.25" in text
    assert "TP" in text


def test_format_trades_html_escapes_exit_reason():
    text = format_trades_html(
        [
            {
                "side": "short",
                "entry_time": "2024-02-01T09:00:00",
                "exit_time": "2024-02-01T09:15:00",
                "entry_price": 100.0,
                "stop_loss": 101.0,
                "take_profit": 98.0,
                "risk_usd": 10.0,
                "pnl": -10.0,
                "exit_reason": "sl<script>",
            }
        ]
    )
    assert "<script>" not in text
    assert "SL&lt;SCRIPT&gt;" in text
