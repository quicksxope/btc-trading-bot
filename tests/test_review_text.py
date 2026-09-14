from datetime import date

from bot.fsm.validation import BacktestDraft
from bot.review_text import hola_result_disclaimer, review_summary_html
from engine.models import BacktestConfig
import yaml


def test_review_cipher_b_30m_hint():
    draft = BacktestDraft(
        instrument=None,
        primary_tf="15m",
        strategy_preset="cipher_b",
        strategy_mode="preset",
    )
    html = review_summary_html(draft)
    assert "30m" in html


def test_hola_disclaimer():
    assert hola_result_disclaimer("holaprime_10k")
    assert hola_result_disclaimer("generic") is None


def test_example_holaprime_preset_yaml_loads():
    path = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "configs/examples/cipher_b_holaprime_1step_30m.yaml"
    )
    raw = yaml.safe_load(path.read_text())
    cfg = BacktestConfig.model_validate(raw)
    assert cfg.strategy.preset == "cipher_b"
    assert cfg.prop_firm.pack_id == "holaprime_1step_10k"
    assert cfg.timeframes.primary == "30m"
    assert cfg.date_range.start == date(2024, 1, 1)
