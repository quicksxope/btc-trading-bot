"""Inline keyboards for wizard and home."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.fsm.validation import BacktestDraft


def nav_row(back_cb: str = "wiz:back", cancel_cb: str = "wiz:cancel") -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(text="« Back", callback_data=back_cb),
        InlineKeyboardButton(text="Cancel", callback_data=cancel_cb),
    ]


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="New backtest", callback_data="home:new"),
                InlineKeyboardButton(text="Indicator study", callback_data="home:study"),
            ],
            [
                InlineKeyboardButton(text="My presets", callback_data="home:presets"),
                InlineKeyboardButton(text="Last results", callback_data="home:last"),
            ],
            [
                InlineKeyboardButton(text="Status", callback_data="home:status"),
                InlineKeyboardButton(text="Help", callback_data="home:help"),
            ],
        ]
    )


def asset_class_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Crypto perpetual", callback_data="wiz:ac:crypto_perp")],
            [InlineKeyboardButton(text="CFD / Macro", callback_data="wiz:ac:cfd")],
            nav_row(),
        ]
    )


def instrument_keyboard(draft: BacktestDraft) -> InlineKeyboardMarkup:
    from engine.catalog import list_instruments_for_asset_class

    rows = []
    if draft.asset_class:
        insts = list_instruments_for_asset_class(draft.asset_class)
        row: list[InlineKeyboardButton] = []
        for inst in insts:
            row.append(
                InlineKeyboardButton(text=inst.value, callback_data=f"wiz:inst:{inst.value}")
            )
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
    rows.append(nav_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def date_preset_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Last 6mo", callback_data="wiz:date:6mo"),
                InlineKeyboardButton(text="Last 1y", callback_data="wiz:date:1y"),
            ],
            [InlineKeyboardButton(text="Max available", callback_data="wiz:date:max")],
            [InlineKeyboardButton(text="Custom…", callback_data="wiz:date:custom")],
            nav_row(),
        ]
    )


def session_keyboard(draft: BacktestDraft) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Asia (00–08 UTC)", callback_data="wiz:sess:asia")],
        [InlineKeyboardButton(text="London (07–16 UTC)", callback_data="wiz:sess:london")],
        [InlineKeyboardButton(text="New York (12–21 UTC)", callback_data="wiz:sess:ny")],
    ]
    if draft.asset_class == "crypto_perp":
        rows.append(
            [InlineKeyboardButton(text="24/7 (crypto)", callback_data="wiz:sess:all_day")]
        )
    rows.append(
        [InlineKeyboardButton(text="Advanced session…", callback_data="wiz:sess:advanced")]
    )
    rows.append(nav_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def session_toggles_keyboard(draft: BacktestDraft) -> InlineKeyboardMarkup:
    t = "✓ Trading" if draft.session_trading else "Trading"
    a = "✓ Accounting" if draft.session_accounting else "Accounting"
    u = "✓ Daily reset UTC" if draft.prop_daily_reset_utc else "Daily reset UTC"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t, callback_data="wiz:stoggle:trade"),
                InlineKeyboardButton(text=a, callback_data="wiz:stoggle:acct"),
            ],
            [InlineKeyboardButton(text=u, callback_data="wiz:stoggle:utc")],
            [InlineKeyboardButton(text="Continue »", callback_data="wiz:stoggle:done")],
            nav_row(),
        ]
    )


def primary_tf_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="15m", callback_data="wiz:ptf:15m"),
                InlineKeyboardButton(text="30m", callback_data="wiz:ptf:30m"),
                InlineKeyboardButton(text="1h", callback_data="wiz:ptf:1h"),
                InlineKeyboardButton(text="4h", callback_data="wiz:ptf:4h"),
            ],
            [
                InlineKeyboardButton(text="1m", callback_data="wiz:ptf:1m"),
                InlineKeyboardButton(text="5m", callback_data="wiz:ptf:5m"),
            ],
            nav_row(),
        ]
    )


def context_tf_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    opts = ["1h", "4h", "1d"]

    def label(tf: str) -> str:
        return f"✓ {tf}" if tf in selected else tf

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label(tf), callback_data=f"wiz:ctf:{tf}") for tf in opts],
            [InlineKeyboardButton(text="Done", callback_data="wiz:ctf:done")],
            nav_row(),
        ]
    )


def strategy_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Preset strategy", callback_data="wiz:str:preset")],
            [InlineKeyboardButton(text="Custom indicators", callback_data="wiz:str:custom")],
            [InlineKeyboardButton(text="Context TF (optional)", callback_data="wiz:str:context")],
            nav_row(),
        ]
    )


def risk_reward_keyboard(draft: "BacktestDraft | None" = None) -> InlineKeyboardMarkup:
    from bot.fsm.validation import BacktestDraft

    d = draft or BacktestDraft()
    rows: list[list[InlineKeyboardButton]] = [_rr_row(d.execution_risk_reward_ratio)]
    rows.append([InlineKeyboardButton(text="Continue »", callback_data="wiz:rr:done")])
    rows.append(nav_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def strategy_preset_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Cipher_B (WT+RSI+Bressert)", callback_data="wiz:sp:cipher_b")],
            [InlineKeyboardButton(text="Trend_EMA_cross", callback_data="wiz:sp:trend_ema_cross")],
            [InlineKeyboardButton(text="RSI_mean_revert", callback_data="wiz:sp:rsi_mean_revert")],
            nav_row(),
        ]
    )


def custom_indicator_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="+ RSI", callback_data="wiz:ci:RSI"),
                InlineKeyboardButton(text="+ EMA", callback_data="wiz:ci:EMA"),
            ],
            [
                InlineKeyboardButton(text="+ MACD", callback_data="wiz:ci:MACD"),
                InlineKeyboardButton(text="+ ATR", callback_data="wiz:ci:ATR"),
            ],
            [InlineKeyboardButton(text="Rule: RSI long", callback_data="wiz:rule:rsi_long")],
            [InlineKeyboardButton(text="Rule: EMA+RSI template", callback_data="wiz:rule:ema_rsi")],
            [InlineKeyboardButton(text="Continue »", callback_data="wiz:ci:done")],
            nav_row(),
        ]
    )


def prop_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Semua paket ter-mapping…", callback_data="wiz:prop:templates")],
            [
                InlineKeyboardButton(
                    text="Hola 1-Step $50K",
                    callback_data="wiz:prop:load:holaprime_1step_50k",
                ),
                InlineKeyboardButton(
                    text="TopStep $50K",
                    callback_data="wiz:prop:load:topstep_50k_combine",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Hola Direct $50K",
                    callback_data="wiz:prop:load:holaprime_direct_50k",
                ),
            ],
            [InlineKeyboardButton(text="Custom (max loss, profit, …)", callback_data="wiz:prop:custom")],
            [InlineKeyboardButton(text="Tanpa prop (PnL saja)", callback_data="wiz:prop:none")],
            nav_row(),
        ]
    )


def prop_template_keyboard() -> InlineKeyboardMarkup:
    from engine.catalog import list_prop_templates_for_wizard

    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for pid, label in list_prop_templates_for_wizard():
        text = label if len(label) <= 28 else label[:25] + "…"
        row.append(InlineKeyboardButton(text=text, callback_data=f"wiz:prop:load:{pid}"))
        if len(row) == 1:
            rows.append(row)
            row = []
    rows.append(nav_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _rr_button(label: str, value: float, current: float | None) -> InlineKeyboardButton:
    mark = " ✓" if current is not None and abs(current - value) < 1e-9 else ""
    return InlineKeyboardButton(text=f"{label}{mark}", callback_data=f"wiz:rr:{value:g}")


def _rr_row(current: float | None) -> list[InlineKeyboardButton]:
    cur = current if current is not None else 2.0
    return [
        _rr_button("1:1", 1.0, cur),
        _rr_button("1:1.5", 1.5, cur),
        _rr_button("1:2", 2.0, cur),
        _rr_button("1:3", 3.0, cur),
    ]


def _consistency_btn(label: str, rule: str, pct: float | None, draft: "BacktestDraft") -> InlineKeyboardButton:
    if rule == "none":
        active = draft.prop_consistency_rule in (None, "", "none")
    elif rule == "hola_best_day":
        active = draft.prop_consistency_rule == "hola_best_day"
    else:
        active = draft.prop_consistency_rule == "topstep_target_ratio"
    mark = " ✓" if active else ""
    if rule == "none":
        cb = "wiz:propp:cons:none"
    elif rule == "hola_best_day":
        cb = "wiz:propp:cons:hola20"
    else:
        cb = "wiz:propp:cons:top50"
    return InlineKeyboardButton(text=f"{label}{mark}", callback_data=cb)


def _consistency_row(draft: "BacktestDraft") -> list[InlineKeyboardButton]:
    return [
        _consistency_btn("Cons off", "none", None, draft),
        _consistency_btn("Cons 20%", "hola_best_day", 20.0, draft),
        _consistency_btn("Cons 50% tgt", "topstep_target_ratio", None, draft),
    ]


def prop_custom_keyboard(draft: "BacktestDraft | None" = None) -> InlineKeyboardMarkup:
    from bot.fsm.validation import BacktestDraft

    d = draft or BacktestDraft()
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="Daily loss 5%", callback_data="wiz:propp:d5"),
            InlineKeyboardButton(text="Daily loss 3%", callback_data="wiz:propp:d3"),
        ],
        [
            InlineKeyboardButton(text="Max loss 10%", callback_data="wiz:propp:dd10"),
            InlineKeyboardButton(text="Max loss 6%", callback_data="wiz:propp:dd6"),
        ],
        [
            InlineKeyboardButton(text="Profit 10%", callback_data="wiz:propp:pt10"),
            InlineKeyboardButton(text="No profit tgt", callback_data="wiz:propp:pt0"),
        ],
        [
            InlineKeyboardButton(text="Min days 2", callback_data="wiz:propp:min2"),
            InlineKeyboardButton(text="Min days 4", callback_data="wiz:propp:min4"),
        ],
    ]
    rows.append(_consistency_row(d))
    rows.append([InlineKeyboardButton(text="Continue »", callback_data="wiz:propp:done")])
    rows.append(nav_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def prop_params_keyboard(draft: "BacktestDraft | None" = None) -> InlineKeyboardMarkup:
    from bot.fsm.validation import BacktestDraft

    d = draft or BacktestDraft()
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="Daily 5%", callback_data="wiz:propp:d5"),
            InlineKeyboardButton(text="Daily 4%", callback_data="wiz:propp:d4"),
        ],
        [
            InlineKeyboardButton(text="Max DD 10%", callback_data="wiz:propp:dd10"),
            InlineKeyboardButton(text="Max DD 8%", callback_data="wiz:propp:dd8"),
        ],
    ]
    rows.append(_consistency_row(d))
    rows.append([InlineKeyboardButton(text="Continue »", callback_data="wiz:propp:done")])
    rows.append(nav_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def balance_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="10k", callback_data="wiz:bal:10000"),
                InlineKeyboardButton(text="50k", callback_data="wiz:bal:50000"),
                InlineKeyboardButton(text="100k", callback_data="wiz:bal:100000"),
            ],
            [InlineKeyboardButton(text="Custom…", callback_data="wiz:bal:custom")],
            nav_row(),
        ]
    )


def review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Run", callback_data="wiz:run")],
            [
                InlineKeyboardButton(text="Ubah periode", callback_data="wiz:review:dates"),
                InlineKeyboardButton(text="Save preset", callback_data="wiz:save_preset"),
            ],
            nav_row(back_cb="wiz:back"),
        ]
    )
