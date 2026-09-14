"""Pydantic config models — shared by CLI, worker, and bot."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class InstrumentId(str, Enum):
    BTC_PERP = "BTC_PERP"
    ETH_PERP = "ETH_PERP"
    SPX500_CFD = "SPX500_CFD"
    NASDAQ_CFD = "NASDAQ_CFD"
    XAUUSD_CFD = "XAUUSD_CFD"


class AssetClass(str, Enum):
    CRYPTO_PERP = "crypto_perp"
    CFD = "cfd"


class SessionId(str, Enum):
    ASIA = "asia"
    LONDON = "london"
    NY = "ny"
    ALL_DAY = "all_day"


class DateRange(BaseModel):
    start: date
    end: date

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        start = info.data.get("start")
        if start and v < start:
            raise ValueError("end must be >= start")
        return v


class SessionConfig(BaseModel):
    id: SessionId
    use_for_trading: bool = True
    use_for_accounting: bool = True


class TimeframeConfig(BaseModel):
    primary: str
    context: list[str] = Field(default_factory=list)


class StrategyConfig(BaseModel):
    mode: Literal["preset", "custom"] = "preset"
    preset: str | None = "trend_ema_cross"
    custom_indicators: list[dict[str, Any]] = Field(default_factory=list)
    custom_rule: str = ""


class PropFirmConfig(BaseModel):
    enabled: bool = True
    pack_id: str = "generic"
    daily_loss_pct: float = 5.0
    max_drawdown_pct: float = 10.0
    profit_target_pct: float | None = None
    min_trading_days: int | None = None


class ExecutionConfig(BaseModel):
    fill: Literal["next_bar_open", "bar_close"] = "next_bar_open"
    initial_balance: float = 100_000.0
    allow_entries_outside_session: bool = False
    allow_exits_outside_session: bool = True
    daily_reset: Literal["utc", "session"] = "session"


class BacktestConfig(BaseModel):
    instrument: InstrumentId
    asset_class: AssetClass
    date_range: DateRange
    session: SessionConfig
    timeframes: TimeframeConfig
    strategy: StrategyConfig
    prop_firm: PropFirmConfig
    execution: ExecutionConfig
    meta: dict[str, Any] = Field(default_factory=dict)

    def to_yaml_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class InstrumentProfile(BaseModel):
    instrument_id: InstrumentId
    asset_class: AssetClass
    data_symbol: str
    contract_size: float = 1.0
    spread_points: float = 0.0
    commission_per_lot: float = 0.0
    fee_bps: float = 4.0
    funding_bps_per_8h: float = 1.0
    leverage: float = 10.0
    point_value: float = 1.0


class BacktestResult(BaseModel):
    net_pnl_pct: float
    max_drawdown_pct: float
    win_rate: float
    trade_count: int
    profit_factor: float
    prop_pass: bool
    prop_fail_reason: str | None = None
    worst_daily_loss_pct: float = 0.0
    trading_days: int = 0
    equity_final: float = 0.0
