"""Validation rules for wizard draft → BacktestConfig."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

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

AssetClassChoice = Literal["crypto_perp", "cfd"]
TIMEFRAME_ORDER = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}


@dataclass
class BacktestDraft:
    """Mutable wizard state before YAML/config materialization."""

    asset_class: AssetClassChoice | None = None
    instrument: InstrumentId | None = None
    date_from: date | None = None
    date_to: date | None = None
    session_id: SessionId | None = None
    session_trading: bool = True
    session_accounting: bool = True
    prop_daily_reset_utc: bool = False
    primary_tf: str | None = None
    context_tfs: list[str] = field(default_factory=list)
    strategy_mode: Literal["preset", "custom"] | None = None
    strategy_preset: str | None = None
    custom_indicators: list[dict] = field(default_factory=list)
    custom_rule: str | None = None
    prop_pack: str | None = "generic"
    prop_daily_loss_pct: float | None = 5.0
    prop_max_dd_pct: float | None = 10.0
    initial_balance: float = 100_000.0
    fill_model: str = "next_bar_open"

    def mini_spec_footer(self) -> str:
        inst = self.instrument.value if self.instrument else "—"
        sess = self.session_id.value if self.session_id else "—"
        toggles = []
        if self.session_trading:
            toggles.append("trade")
        if self.session_accounting:
            toggles.append("acct")
        sess_s = f"{sess} ({'+'.join(toggles) or 'off'})" if sess != "—" else "—"
        tf = self.primary_tf or "—"
        ctx = ",".join(self.context_tfs) if self.context_tfs else "—"
        prop = self.prop_pack or "none"
        if self.prop_pack and self.prop_pack != "none":
            prop = f"{prop} {self.prop_max_dd_pct}%"
        return (
            f"Instrument: {inst} | Session: {sess_s} | "
            f"TF: {tf} + {ctx} | Prop: {prop} | Fill: next bar open"
        )


class ValidationError(Exception):
    def __init__(self, message: str, step_hint: str | None = None):
        super().__init__(message)
        self.step_hint = step_hint


def _instruments_for_class(ac: AssetClassChoice) -> set[InstrumentId]:
    if ac == "crypto_perp":
        return {InstrumentId.BTC_PERP, InstrumentId.ETH_PERP}
    return {
        InstrumentId.SPX500_CFD,
        InstrumentId.NASDAQ_CFD,
        InstrumentId.XAUUSD_CFD,
    }


def validate_asset_class(draft: BacktestDraft) -> None:
    if draft.asset_class not in ("crypto_perp", "cfd"):
        raise ValidationError("Pilih asset class.", "asset_class")


def validate_instrument(draft: BacktestDraft) -> None:
    validate_asset_class(draft)
    if draft.instrument is None:
        raise ValidationError("Pilih instrument.", "instrument")
    allowed = _instruments_for_class(draft.asset_class)  # type: ignore[arg-type]
    if draft.instrument not in allowed:
        raise ValidationError("Instrument tidak cocok dengan asset class.", "instrument")


def validate_date_range(draft: BacktestDraft) -> None:
    if not draft.date_from or not draft.date_to:
        raise ValidationError("Pilih rentang tanggal.", "date_range")
    if draft.date_from > draft.date_to:
        raise ValidationError("Tanggal mulai harus sebelum tanggal akhir.", "date_range")
    if draft.date_to > date.today():
        raise ValidationError("Tanggal akhir tidak boleh di masa depan.", "date_range")


def validate_session(draft: BacktestDraft) -> None:
    validate_instrument(draft)
    is_crypto = draft.asset_class == "crypto_perp"
    if draft.session_id is None:
        raise ValidationError("Pilih session.", "session")
    if draft.session_id == SessionId.ALL_DAY and not is_crypto:
        raise ValidationError("24/7 hanya untuk crypto perpetual.", "session")
    if not draft.session_trading and not draft.session_accounting:
        raise ValidationError("Nyalakan trading atau accounting session.", "session_toggles")


def validate_timeframes(draft: BacktestDraft) -> None:
    if not draft.primary_tf or draft.primary_tf not in TIMEFRAME_ORDER:
        raise ValidationError("Pilih primary timeframe.", "timeframes_primary")
    p = TIMEFRAME_ORDER[draft.primary_tf]
    for c in draft.context_tfs:
        if c not in TIMEFRAME_ORDER:
            raise ValidationError(f"Context TF tidak valid: {c}", "timeframes_context")
        if TIMEFRAME_ORDER[c] <= p:
            raise ValidationError(
                f"Context {c} harus lebih besar dari primary {draft.primary_tf}.",
                "timeframes_context",
            )


def validate_strategy(draft: BacktestDraft) -> None:
    if draft.strategy_mode == "preset":
        if not draft.strategy_preset:
            raise ValidationError("Pilih strategy preset.", "strategy_preset")
    elif draft.strategy_mode == "custom":
        if not draft.custom_indicators:
            raise ValidationError("Tambah minimal satu indicator.", "strategy_custom")
        if not draft.custom_rule:
            raise ValidationError("Definisikan rule entry.", "strategy_custom")
    else:
        raise ValidationError("Pilih mode strategy.", "strategy_mode")


def validate_prop(draft: BacktestDraft) -> None:
    if draft.prop_pack in (None, "none"):
        return
    if draft.prop_daily_loss_pct is None or draft.prop_max_dd_pct is None:
        raise ValidationError("Isi daily loss dan max DD.", "prop_firm")
    if not (0 < draft.prop_daily_loss_pct <= 100):
        raise ValidationError("Daily loss % harus 0–100.", "prop_firm")
    if not (0 < draft.prop_max_dd_pct <= 100):
        raise ValidationError("Max DD % harus 0–100.", "prop_firm")


def validate_balance(draft: BacktestDraft) -> None:
    if draft.initial_balance <= 0:
        raise ValidationError("Balance awal harus positif.", "execution_balance")


def validate_full(draft: BacktestDraft) -> None:
    validate_instrument(draft)
    validate_date_range(draft)
    validate_session(draft)
    validate_timeframes(draft)
    validate_strategy(draft)
    validate_prop(draft)
    validate_balance(draft)


def draft_to_config(draft: BacktestDraft) -> BacktestConfig:
    validate_full(draft)
    assert draft.instrument and draft.date_from and draft.date_to and draft.session_id
    assert draft.primary_tf and draft.strategy_mode

    ac = AssetClass.CRYPTO_PERP if draft.asset_class == "crypto_perp" else AssetClass.CFD

    if draft.prop_pack in (None, "none"):
        prop = PropFirmConfig(enabled=False)
    else:
        prop = PropFirmConfig(
            enabled=True,
            pack_id=draft.prop_pack or "generic",
            daily_loss_pct=draft.prop_daily_loss_pct or 5.0,
            max_drawdown_pct=draft.prop_max_dd_pct or 10.0,
        )

    if draft.strategy_mode == "preset":
        strategy = StrategyConfig(mode="preset", preset=draft.strategy_preset)
    else:
        strategy = StrategyConfig(
            mode="custom",
            custom_indicators=draft.custom_indicators,
            custom_rule=draft.custom_rule or "",
        )

    daily_reset = "utc" if draft.prop_daily_reset_utc else "session"

    return BacktestConfig(
        instrument=draft.instrument,
        asset_class=ac,
        date_range=DateRange(start=draft.date_from, end=draft.date_to),
        session=SessionConfig(
            id=draft.session_id,
            use_for_trading=draft.session_trading,
            use_for_accounting=draft.session_accounting,
        ),
        timeframes=TimeframeConfig(primary=draft.primary_tf, context=list(draft.context_tfs)),
        strategy=strategy,
        prop_firm=prop,
        execution=ExecutionConfig(
            fill=draft.fill_model,
            initial_balance=draft.initial_balance,
            allow_entries_outside_session=False,
            allow_exits_outside_session=True,
            daily_reset=daily_reset,
        ),
        meta={"created_at": datetime.utcnow().isoformat() + "Z"},
    )
