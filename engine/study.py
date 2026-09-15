"""Indicator study — sweep subsets with default AND templates."""

from __future__ import annotations

import json
from collections.abc import Callable
from itertools import combinations
from typing import Any

from engine.backtest import load_backtest_frames, simulate_backtest
from engine.strategy import build_signals
from engine.catalog import indicator_meta, load_rule_templates, sweep_template_id
from engine.models import BacktestConfig, BacktestResult, CustomRulesV2, StrategyConfig

ProgressCallback = Callable[[str, float], None]


def indicator_subsets(pool: list[str]) -> list[tuple[str, ...]]:
    ids = sorted({p.upper() for p in pool})
    out: list[tuple[str, ...]] = []
    for k in range(1, len(ids) + 1):
        out.extend(combinations(ids, k))
    return out


def mix_label(mix: tuple[str, ...]) -> str:
    return "+".join(mix)


def signal_stats(
    strategy: StrategyConfig,
    primary,
    context_frames,
    context_idx,
) -> dict[str, int]:
    sig = build_signals(strategy, primary, context_frames, context_idx)
    return {
        "signal_bars_long": int((sig == 1).sum()),
        "signal_bars_short": int((sig == -1).sum()),
        "signal_flips": int((sig.diff().fillna(0) != 0).sum()),
    }


def _spec_key(spec: dict) -> str:
    return json.dumps(
        {
            "name": spec.get("name"),
            "timeframe": spec.get("timeframe", "primary"),
            "params": spec.get("params") or {},
        },
        sort_keys=True,
    )


def _default_params(indicator_id: str) -> dict:
    params: dict[str, Any] = {}
    for pname, pdef in (indicator_meta(indicator_id).get("params") or {}).items():
        params[pname] = pdef.get("default", 14)
    return params


def strategy_for_mix(mix: tuple[str, ...]) -> StrategyConfig:
    templates = load_rule_templates().get("templates", {})
    long_parts: list[str] = []
    short_parts: list[str] = []
    seen: set[str] = set()
    indicators: list[dict] = []

    for ind in mix:
        tid = sweep_template_id(ind)
        if not tid:
            raise ValueError(f"No sweep template for {ind}")
        t = templates.get(tid)
        if not t:
            raise ValueError(f"Unknown template {tid}")
        if t.get("long_when"):
            long_parts.append(f"({t['long_when']})")
        if t.get("short_when"):
            short_parts.append(f"({t['short_when']})")
        for spec in t.get("requires_indicators") or []:
            key = _spec_key(spec)
            if key in seen:
                continue
            seen.add(key)
            name = spec.get("name", ind)
            indicators.append(
                {
                    "name": name,
                    "timeframe": spec.get("timeframe", "primary"),
                    "params": spec.get("params") or _default_params(name),
                }
            )

    if not indicators:
        for ind in mix:
            indicators.append(
                {"name": ind, "timeframe": "primary", "params": _default_params(ind)}
            )

    return StrategyConfig(
        mode="custom",
        custom_indicators=indicators,
        custom_rules_v2=CustomRulesV2(
            long_when=" and ".join(long_parts),
            short_when=" and ".join(short_parts),
        ),
    )


def _result_sort_key(result: BacktestResult, prop_enabled: bool) -> tuple:
    tier = 0 if (not prop_enabled or result.prop_pass) else 1
    return (tier, -result.net_pnl_pct)


def rank_study_rows(
    rows: list[dict[str, Any]], *, prop_enabled: bool
) -> list[dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda r: _result_sort_key(
            BacktestResult.model_validate(r["result"]), prop_enabled
        ),
    )
    for i, row in enumerate(ranked, 1):
        row["rank"] = i
    return ranked


def run_indicator_study(
    config: BacktestConfig,
    indicator_pool: list[str],
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    def prog(stage: str, pct: float) -> None:
        if on_progress:
            on_progress(stage, pct)

    if not indicator_pool:
        raise ValueError("indicator_pool is empty")

    missing = [ind for ind in indicator_pool if not sweep_template_id(ind)]
    if missing:
        raise ValueError(f"Missing sweep templates: {', '.join(missing)}")

    from engine.data_ensure import ensure_bars_for_config

    ensure_bars_for_config(config, on_progress=prog)
    prog("Loading data", 20)
    primary, context_frames, context_idx, profile = load_backtest_frames(config)

    subsets = indicator_subsets(indicator_pool)
    n = len(subsets)
    rows: list[dict[str, Any]] = []
    prop_on = config.prop_firm.enabled

    for i, mix in enumerate(subsets):
        base_pct = 25 + (i / max(n, 1)) * 65
        prog(f"Mix {mix_label(mix)} ({i + 1}/{n})", base_pct)
        cfg = config.model_copy(deep=True)
        cfg.strategy = strategy_for_mix(mix)
        cfg.timeframes = cfg.timeframes.model_copy(update={"context": []})
        stats = signal_stats(cfg.strategy, primary, context_frames, context_idx)
        result, _, trades_df, _, _ = simulate_backtest(
            cfg, primary, context_frames, context_idx, profile
        )
        row: dict[str, Any] = {
            "mix": list(mix),
            "mix_label": mix_label(mix),
            "result": result.model_dump(),
            **stats,
        }
        if not trades_df.empty:
            row["_trades"] = json.loads(
                trades_df.to_json(orient="records", date_format="iso")
            )
        rows.append(row)

    ranked = rank_study_rows(rows, prop_enabled=prop_on)
    best = ranked[0] if ranked else None
    pass_count = sum(1 for r in ranked if r["result"].get("prop_pass"))
    # Transient: worker writes trades.csv then pops before finish_job (keep result_json lean).
    best_trades: list[dict] = list((best or {}).get("_trades") or [])
    for row in ranked:
        row.pop("_trades", None)

    prog("Done", 100)
    return {
        "kind": "indicator_study",
        "indicator_pool": sorted({p.upper() for p in indicator_pool}),
        "mix_count": n,
        "pass_count": pass_count,
        "best_mix": best["mix"] if best else [],
        "best_mix_label": best["mix_label"] if best else "",
        "best": best["result"] if best else None,
        "best_trades": best_trades,
        "rows": ranked,
    }
