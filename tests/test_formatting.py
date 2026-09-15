from bot.formatting import fit_telegram_html


def test_fit_telegram_html_passthrough():
    assert fit_telegram_html("hello", limit=100) == "hello"


def test_fit_telegram_html_truncates_at_newline():
    text = "line1\n" + ("x" * 80) + "\nline3"
    out = fit_telegram_html(text, limit=40)
    assert len(out) <= 40
    assert out.endswith("…truncated</i>")
    assert "line1" in out
